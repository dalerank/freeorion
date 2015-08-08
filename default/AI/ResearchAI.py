from functools import partial
import math
import random

import freeOrionAIInterface as fo  # pylint: disable=import-error
import FreeOrionAI as foAI
import TechsListsAI
import AIDependencies
import AIstate
import ColonisationAI
import ShipDesignAI
from freeorion_tools import tech_is_complete, get_ai_tag_grade

inProgressTechs = {}

empire_stars = {}
research_reqs = {}
choices = {}

REQS_PREREQS_IDX = 0
REQS_COST_IDX = 1
REQS_TIME_IDX = 2
REQS_PER_TURN_COST_IDX = 3


# TODO research AI no longer use this method, rename and move this method elsewhere
def get_research_index():
    empire_id = fo.empireID()
    research_index = empire_id % 2
    if foAI.foAIstate.aggression >= fo.aggression.aggressive:  # maniacal
        research_index = 2 + (empire_id % 3)  # so indices [2,3,4]
    elif foAI.foAIstate.aggression >= fo.aggression.typical:
        research_index += 1
    return research_index


def const_priority(this_const=0.0, tech_name=""):
    """
    returns a constant priority
    :type this_const: float
    :type tech_name: str
    :rtype float
    """
    return this_const


# because this constant is used so often
def priority_zero(tech_name=""):
    """
    returns a constant 0.0 priority
    :type tech_name: str
    :rtype float
    """
    return 0.0


# because this constant is used so often
def priority_low(tech_name=""):
    """
    returns a constant 0.0 priority
    :type tech_name: str
    :rtype float
    """
    return 0.1


# because this constant is used so often
def priority_one(tech_name=""):
    """
    returns a constant 0.0 priority
    :type tech_name: str
    :rtype float
    """
    return 1.0


def conditional_priority(func_if_true, func_if_false, cond_func=None, this_object=None, this_attr=None, tech_name=""):
    """
    returns a priority dependent on a condition, either a function or an object attribute
    :type func_if_true: () -> bool
    :type func_if_false: () -> bool
    :type cond_func:(str) -> bool
    :type this_object: object
    :type this_attr:str
    :type tech_name:str
    :rtype float
    """
    if cond_func is None:
        if this_object is not None:
            cond_func = partial(getattr, this_object, this_attr)
        else:
            return priority_low()
    if cond_func():
        return func_if_true(tech_name)
    else:
        return func_if_false(tech_name)

MIL_IDX = 0
TROOP_IDX = 1
COLONY_IDX = 2

MAIN_SHIP_DESIGNER_LIST = []


def get_main_ship_designer_list():
    if not MAIN_SHIP_DESIGNER_LIST:
        MAIN_SHIP_DESIGNER_LIST.extend([ShipDesignAI.MilitaryShipDesigner(), ShipDesignAI.StandardTroopShipDesigner(),
                                        ShipDesignAI.StandardColonisationShipDesigner()])
    return MAIN_SHIP_DESIGNER_LIST


def ship_usefulness(base_priority_func, this_designer=None, tech_name=""):
    """

    :type base_priority_func: () _> bool
    :type this_designer: int | None
    """
    if this_designer is None:
        this_designer_list = get_main_ship_designer_list()
    elif isinstance(this_designer, int):
        this_designer_list = get_main_ship_designer_list()[:this_designer+1][-1:]
    else:
        return 0.0
    useful = 0.0
    for this_designer in this_designer_list:
        useful = max(useful, get_ship_tech_usefulness(tech_name, this_designer))
    return useful * base_priority_func()


def has_star(star_type):
    if star_type not in empire_stars:
        empire_stars[star_type] = len(AIstate.empireStars.get(star_type, [])) != 0
    return empire_stars[star_type]


def if_enemies(false_val=0.1, true_val=1.0, tech_name=""):
    return true_val if foAI.foAIstate.misc.get('enemies_sighted', {}) else false_val


def if_dict(this_dict, this_key, false_val=0.1, true_val=1.0, tech_name=""):
    return true_val if this_dict.get(this_key, False) else false_val


def if_tech_target(tech_target, false_val=0.1, true_val=1.0, tech_name=""):
    return true_val if tech_is_complete(tech_target) else false_val


def has_only_bad_colonizers():
    most_adequate = 0
    for specName in ColonisationAI.empire_colonizers:
        environs = {}
        this_spec = fo.getSpecies(specName)
        if not this_spec:
            continue
        for ptype in [fo.planetType.swamp, fo.planetType.radiated, fo.planetType.toxic, fo.planetType.inferno,
                      fo.planetType.barren, fo.planetType.tundra, fo.planetType.desert, fo.planetType.terran,
                      fo.planetType.ocean, fo.planetType.asteroids]:
            environ = this_spec.getPlanetEnvironment(ptype)
            environs.setdefault(environ, []).append(ptype)
        most_adequate = max(most_adequate, len(environs.get(fo.planetEnvironment.adequate, [])))
    return most_adequate == 0


def get_max_stealth_species():
    stealth_grades = {'BAD': -15, 'GOOD': 15, 'GREAT': 40, 'ULTIMATE': 60}
    stealth = -999
    stealth_species = ""
    for specName in ColonisationAI.empire_colonizers:
        this_spec = fo.getSpecies(specName)
        if not this_spec:
            continue
        this_stealth = stealth_grades.get(get_ai_tag_grade(list(this_spec.tags), "STEALTH"), 0)
        if this_stealth > stealth:
            stealth_species = specName
            stealth = this_stealth
    result = (stealth_species, stealth)
    return result


def get_initial_research_target():
    # TODO: consider cases where may want lesser target
    return AIDependencies.ART_MINDS


def get_ship_tech_usefulness(tech, ship_designer):
    this_tech = fo.getTech(tech)
    if not this_tech:
        print "Invalid Tech specified"
        return 0
    unlocked_items = this_tech.unlockedItems
    unlocked_hulls = []
    unlocked_parts = []
    for item in unlocked_items:
        if item.type == fo.unlockableItemType.shipPart:
            unlocked_parts.append(item.name)
        elif item.type == fo.unlockableItemType.shipHull:
            unlocked_hulls.append(item.name)
    if not (unlocked_parts or unlocked_hulls):
        return 0
    old_designs = ship_designer.optimize_design(consider_fleet_count=False)
    new_designs = ship_designer.optimize_design(additional_hulls=unlocked_hulls, additional_parts=unlocked_parts,
                                                consider_fleet_count=False)
    if not (old_designs and new_designs):
        # AI is likely defeated; don't bother with logging error message
        return 0
    old_rating, old_pid, old_design_id, old_cost = old_designs[0]
    old_rating = old_rating
    new_rating, new_pid, new_design_id, new_cost = new_designs[0]
    new_rating = new_rating
    if new_rating > old_rating:
        ratio = (new_rating - old_rating) / (new_rating + old_rating)
        return ratio * 1.5 + 0.5
    else:
        return 0


def get_population_boost_priority(tech_name=""):
    return 2


def get_stealth_priority(tech_name=""):
    max_stealth_species = get_max_stealth_species()
    if max_stealth_species[1] > 0:
        print "Has a stealthy species %s. Increase stealth tech priority" % max_stealth_species[0]
        return 1.5
    else:
        return 0.1


def get_xeno_genetics_priority(tech_name=""):
    if foAI.foAIstate.aggression < fo.aggression.cautious:
        return get_population_boost_priority()
    if has_only_bad_colonizers():
        # Empire only have lousy colonisers, xeno-genetics are really important for them
        print "Empire has only lousy colonizers, increase priority to xeno_genetics"
        return get_population_boost_priority() * 3
    else:
        # TODO: assess number of planets with Adequate/Poor planets owned or considered for colonies
        return 0.6 * get_population_boost_priority()


def get_artificial_black_hole_priority(tech_name=""):
    if has_star(fo.starType.blackHole) or not has_star(fo.starType.red):
        print "Already have black hole, or does not have a red star to turn to black hole. Skipping ART_BLACK_HOLE"
        return 0
    for tech in AIDependencies.SHIP_TECHS_REQUIRING_BLACK_HOLE:
        if tech_is_complete(tech):
            print "Solar hull is researched, needs a black hole to produce it. Research ART_BLACK_HOLE now!"
            return 999
    return 1


def get_hull_priority(tech_name):
    hull = 1
    offtrack_hull = 0.05

    chosen_hull = choices['hull']
    organic = hull if chosen_hull % 2 == 0 or choices['extra_organic_hull'] else offtrack_hull
    robotic = hull if chosen_hull % 2 == 1 or choices['extra_robotic_hull'] else offtrack_hull
    if ColonisationAI.got_ast:
        extra = choices['extra_asteroid_hull']
        asteroid = hull if chosen_hull == 2 or extra else offtrack_hull
        if asteroid == hull and not extra:
            organic = offtrack_hull
            robotic = offtrack_hull
    else:
        asteroid = 0
    if has_star(fo.starType.blue) or has_star(fo.starType.blackHole):
        extra = choices['extra_energy_hull']
        energy = hull if chosen_hull == 3 or extra else offtrack_hull
        if energy == hull and not extra:
            organic = offtrack_hull
            robotic = offtrack_hull
            asteroid = offtrack_hull
    else:
        energy = 0

    useful = max(
        get_ship_tech_usefulness(tech_name, ShipDesignAI.MilitaryShipDesigner()),
        get_ship_tech_usefulness(tech_name, ShipDesignAI.StandardTroopShipDesigner()),
        get_ship_tech_usefulness(tech_name, ShipDesignAI.StandardColonisationShipDesigner()))

    if foAI.foAIstate.misc.get('enemies_sighted', {}):
        aggression = 1
    else:
        aggression = 0.1

    if tech_name in AIDependencies.ROBOTIC_HULL_TECHS:
        return robotic * useful * aggression
    elif tech_name in AIDependencies.ORGANIC_HULL_TECHS:
        return organic * useful * aggression
    elif tech_name in AIDependencies.ASTEROID_HULL_TECHS:
        return asteroid * useful * aggression
    elif tech_name in AIDependencies.ENERGY_HULL_TECHS:
        return energy * useful * aggression
    else:
        return useful * aggression

# TODO boost genome bank if enemy is using bioterror
# TODO for supply techs consider starlane density and planet density

# initializing priority functions here within generate_research_orders() to avoid import race

# keys are "PREFIX1", as in "DEF" or "SPY"
primary_prefix_priority_funcs = {}

# keys are "PREFIX1_PREFIX2", as in "SHP_WEAPON"
secondary_prefix_priority_funcs = {}

# keys are individual full tech names
priority_funcs = {}

DEFAULT_PRIORITY = 0.5


def get_priority(tech_name):
    """
    Get tech priority. the default is just above. 0 if not useful (but doesn't hurt to research),
    < 0 to prevent AI to research it
    """
    name_parts = tech_name.split('_')
    primary_prefix = name_parts[0]
    secondary_prefix = '_'.join(name_parts[:2])
    if tech_name in priority_funcs:
        return priority_funcs[tech_name](tech_name=tech_name)
    elif secondary_prefix in secondary_prefix_priority_funcs:
        return secondary_prefix_priority_funcs[secondary_prefix](tech_name=tech_name)
    elif primary_prefix in primary_prefix_priority_funcs:
        return primary_prefix_priority_funcs[primary_prefix](tech_name=tech_name)

    # default priority for unseen techs
    if not tech_is_complete(tech_name):
        print "Tech %s does not have a priority, falling back to default." % tech_name

    return DEFAULT_PRIORITY


def calculate_research_requirements():
    """calculate RPs and prerequisites of every tech, in (prereqs, cost, time)"""
    empire = fo.getEmpire()
    research_reqs.clear()

    completed_techs = get_completed_techs()
    for tech_name in fo.techs():
        if tech_is_complete(tech_name):
            research_reqs[tech_name] = ([], 0, 0, 0)
            continue
        this_tech = fo.getTech(tech_name)
        prereqs = [preReq for preReq in this_tech.recursivePrerequisites(empire.empireID) if preReq not in completed_techs]
        base_cost = this_tech.researchCost(empire.empireID)
        progress = empire.researchProgress(tech_name)
        cost = max(0.0, base_cost - progress)
        proportion_remaining = cost / max(base_cost, 1.0)
        this_time = this_tech.researchTime(fo.empireID())
        turns_needed = max(1, math.ceil(proportion_remaining * this_time))  # even if fully paid needs one turn
        per_turn_cost = float(base_cost) / max(1.0, this_time)

        # TODO: the following timing calc treats prereqs as inherently sequential; consider in parallel when able
        for prereq in prereqs:
            prereq_tech = fo.getTech(prereq)
            if not prereq_tech:
                continue
            base_cost = prereq_tech.researchCost(empire.empireID)
            progress = empire.researchProgress(prereq)
            prereq_cost = max(0.0, base_cost - progress)
            proportion_remaining = prereq_cost / max(base_cost, 1.0)
            this_time = prereq_tech.researchTime(fo.empireID())
            turns_needed += max(1, math.ceil(proportion_remaining * this_time))
            cost += prereq_cost
        research_reqs[tech_name] = (prereqs, cost, turns_needed, per_turn_cost)


def tech_cost_sort_key(tech_name):
    return research_reqs.get(tech_name, ([], 0, 0, 0))[REQS_COST_IDX]


def tech_time_sort_key(tech_name):
    return research_reqs.get(tech_name, ([], 0, 0, 0))[REQS_TIME_IDX]


def generate_classic_research_orders():
    """generate research orders"""
    report_adjustments = False
    empire = fo.getEmpire()
    empire_id = empire.empireID
    enemies_sighted = foAI.foAIstate.misc.get('enemies_sighted', {})
    galaxy_is_sparse = ColonisationAI.galaxy_is_sparse()
    print "Research Queue Management:"
    resource_production = empire.resourceProduction(fo.resourceType.research)
    print "\nTotal Current Research Points: %.2f\n" % resource_production
    print "Techs researched and available for use:"
    completed_techs = sorted(list(get_completed_techs()))
    tlist = completed_techs+3*[" "]
    tlines = zip(tlist[0::3], tlist[1::3], tlist[2::3])
    for tline in tlines:
        print "%25s %25s %25s" % tline
    print
    
    #
    # report techs currently at head of research queue
    #
    research_queue = empire.researchQueue
    research_queue_list = get_research_queue_techs()
    total_rp = empire.resourceProduction(fo.resourceType.research)
    inProgressTechs.clear()
    tech_turns_left = {}
    if research_queue_list:
        print "Techs currently at head of Research Queue:"
        for element in list(research_queue)[:10]:
            tech_turns_left[element.tech] = element.turnsLeft
            if element.allocation > 0.0:
                inProgressTechs[element.tech] = True
            this_tech = fo.getTech(element.tech)
            if not this_tech:
                print "Error: can't retrieve tech ", element.tech
                continue
            missing_prereqs = [preReq for preReq in this_tech.recursivePrerequisites(empire_id) if preReq not in completed_techs]
            # unlocked_items = [(uli.name, uli.type) for uli in this_tech.unlocked_items]
            unlocked_items = [uli.name for uli in this_tech.unlockedItems]
            if not missing_prereqs:
                print "    %25s allocated %6.2f RP -- unlockable items: %s " % (element.tech, element.allocation, unlocked_items)
            else:
                print "    %25s allocated %6.2f RP -- missing preReqs: %s -- unlockable items: %s " % (element.tech, element.allocation, missing_prereqs, unlocked_items)
        print
    #
    # set starting techs, or after turn 100 add any additional default techs
    #
    if (fo.currentTurn() == 1) or ((total_rp - research_queue.totalSpent) > 0):
        research_index = get_research_index()
        if fo.currentTurn() == 1:
            # do only this one on first turn, to facilitate use of a turn-1 savegame for testing of alternate
            # research strategies
            new_tech = ["GRO_PLANET_ECOL", "LRN_ALGO_ELEGANCE"]
        else:
            new_tech = TechsListsAI.sparse_galaxy_techs(research_index) if galaxy_is_sparse else TechsListsAI.primary_meta_techs(research_index)
        print "Empire %s (%d) is selecting research index %d" % (empire.name, empire_id, research_index)
        # techs_to_enqueue = (set(new_tech)-(set(completed_techs)|set(research_queue_list)))
        techs_to_enqueue = new_tech[:]
        tech_base = set(completed_techs+research_queue_list)
        techs_to_add = []
        for tech in techs_to_enqueue:
            if tech not in tech_base:
                this_tech = fo.getTech(tech)
                if this_tech is None:
                    print "Error: desired tech '%s' appears to not exist" % tech
                    continue
                missing_prereqs = [preReq for preReq in this_tech.recursivePrerequisites(empire_id) if preReq not in tech_base]
                techs_to_add.extend(missing_prereqs + [tech])
                tech_base.update(missing_prereqs+[tech])
        cum_cost = 0
        print "  Enqueued Tech: %20s \t\t %8s \t %s" % ("Name", "Cost", "CumulativeCost")
        for name in techs_to_add:
            try:
                enqueue_res = fo.issueEnqueueTechOrder(name, -1)
                if enqueue_res == 1:
                    this_tech = fo.getTech(name)
                    this_cost = 0
                    if this_tech:
                        this_cost = this_tech.researchCost(empire_id)
                        cum_cost += this_cost
                    print "    Enqueued Tech: %20s \t\t %8.0f \t %8.0f" % (name, this_cost, cum_cost)
                else:
                    print "    Error: failed attempt to enqueued Tech: " + name
            except:
                print "    Error: failed attempt to enqueued Tech: " + name
                print "    Error: exception triggered and caught: ", traceback.format_exc()


        print "\n\nAll techs:"
        alltechs = fo.techs()  # returns names of all techs
        for tname in alltechs:
            print tname
        print "\n-------------------------------\nAll unqueued techs:"
        # coveredTechs = new_tech+completed_techs
        for tname in [tn for tn in alltechs if tn not in tech_base]:
            print tname

        if fo.currentTurn() == 1:
            return
        if foAI.foAIstate.aggression <= fo.aggression.cautious:
            research_queue_list = get_research_queue_techs()
            def_techs = TechsListsAI.defense_techs_1()
            for def_tech in def_techs:
                if def_tech not in research_queue_list[:5] and not tech_is_complete(def_tech):
                    res = fo.issueEnqueueTechOrder(def_tech, min(3, len(research_queue_list)))
                    print "Empire is very defensive, so attempted to fast-track %s, got result %d" % (def_tech, res)
        if False and foAI.foAIstate.aggression >= fo.aggression.aggressive:  # with current stats of Conc Camps, disabling this fast-track
            research_queue_list = get_research_queue_techs()
            if "CON_CONC_CAMP" in research_queue_list:
                insert_idx = min(40, research_queue_list.index("CON_CONC_CAMP"))
            else:
                insert_idx = max(0, min(40, len(research_queue_list)-10))
            if "SHP_DEFLECTOR_SHIELD" in research_queue_list:
                insert_idx = min(insert_idx, research_queue_list.index("SHP_DEFLECTOR_SHIELD"))
            for cc_tech in ["CON_ARCH_PSYCH", "CON_CONC_CAMP"]:
                if cc_tech not in research_queue_list[:insert_idx + 1] and not tech_is_complete(cc_tech):
                    res = fo.issueEnqueueTechOrder(cc_tech, insert_idx)
                    msg = "Empire is very aggressive, so attempted to fast-track %s, got result %d" % (cc_tech, res)
                    if report_adjustments:
                        chat_human(msg)
                    else:
                        print msg

    elif fo.currentTurn() > 100:
        generate_default_research_order()

    research_queue_list = get_research_queue_techs()
    num_techs_accelerated = 1  # will ensure leading tech doesn't get dislodged
    got_ggg_tech = tech_is_complete("PRO_ORBITAL_GEN")
    got_sym_bio = tech_is_complete("GRO_SYMBIOTIC_BIO")
    got_xeno_gen = tech_is_complete("GRO_XENO_GENETICS")
    #
    # Consider accelerating techs; priority is
    # Supply/Detect range
    # xeno arch
    # ast / GG
    # gro xeno gen
    # distrib thought
    # quant net
    # pro sing gen
    # death ray 1 cleanup

    nest_tech = AIDependencies.NEST_DOMESTICATION_TECH
    artif_minds = AIDependencies.ART_MINDS
    if ColonisationAI.got_nest and not tech_is_complete(nest_tech):
        if artif_minds in research_queue_list:
            insert_idx = 1 + research_queue_list.index(artif_minds)
        else:
            insert_idx = 1
        res = fo.issueEnqueueTechOrder(nest_tech, insert_idx)
        num_techs_accelerated += 1
        msg = "Have a monster nest, so attempted to fast-track %s, got result %d" % (nest_tech, res)
        if report_adjustments:
            chat_human(msg)
        else:
            print msg
        research_queue_list = get_research_queue_techs()

    #
    # Supply range and detection range
    if False:  # disabled for now, otherwise just to help with cold-folding / organization
        if len(foAI.foAIstate.colonisablePlanetIDs) == 0:
            best_colony_site_score = 0
        else:
            best_colony_site_score = foAI.foAIstate.colonisablePlanetIDs.items()[0][1]
        if len(foAI.foAIstate.colonisableOutpostIDs) == 0:
            best_outpost_site_score = 0
        else:
            best_outpost_site_score = foAI.foAIstate.colonisableOutpostIDs.items()[0][1]
        need_improved_scouting = (best_colony_site_score < 150 or best_outpost_site_score < 200)

        if need_improved_scouting:
            if not tech_is_complete("CON_ORBITAL_CON"):
                num_techs_accelerated += 1
                if ("CON_ORBITAL_CON" not in research_queue_list[:1 + num_techs_accelerated]) and (
                        tech_is_complete("PRO_FUSION_GEN") or ("PRO_FUSION_GEN" in research_queue_list[:1 + num_techs_accelerated])):
                    res = fo.issueEnqueueTechOrder("CON_ORBITAL_CON", num_techs_accelerated)
                    msg = "Empire has poor colony/outpost prospects, so attempted to fast-track %s, got result %d" % ("CON_ORBITAL_CON", res)
                    if report_adjustments:
                        chat_human(msg)
                    else:
                        print msg
            elif not tech_is_complete("CON_CONTGRAV_ARCH"):
                num_techs_accelerated += 1
                if ("CON_CONTGRAV_ARCH" not in research_queue_list[:1+num_techs_accelerated]) and (
                        tech_is_complete("CON_METRO_INFRA")):
                    for supply_tech in [_s_tech for _s_tech in ["CON_ARCH_MONOFILS", "CON_CONTGRAV_ARCH"] if not tech_is_complete(_s_tech)]:
                        res = fo.issueEnqueueTechOrder(supply_tech, num_techs_accelerated)
                        msg = "Empire has poor colony/outpost prospects, so attempted to fast-track %s, got result %d" % (supply_tech, res)
                        if report_adjustments:
                            chat_human(msg)
                        else:
                            print msg
            elif not tech_is_complete("CON_GAL_INFRA"):
                num_techs_accelerated += 1
                if ("CON_GAL_INFRA" not in research_queue_list[:1+num_techs_accelerated]) and (
                        tech_is_complete("PRO_SINGULAR_GEN")):
                    res = fo.issueEnqueueTechOrder("CON_GAL_INFRA", num_techs_accelerated)
                    msg = "Empire has poor colony/outpost prospects, so attempted to fast-track %s, got result %d" % ("CON_GAL_INFRA", res)
                    if report_adjustments:
                        chat_human(msg)
                    else:
                        print msg
            else:
                pass
            research_queue_list = get_research_queue_techs()
            # could add more supply tech

            if False and not tech_is_complete("SPY_DETECT_2"):  # disabled for now, detect2
                num_techs_accelerated += 1
                if "SPY_DETECT_2" not in research_queue_list[:2+num_techs_accelerated] and tech_is_complete("PRO_FUSION_GEN"):
                    if "CON_ORBITAL_CON" not in research_queue_list[:1+num_techs_accelerated]:
                        res = fo.issueEnqueueTechOrder("SPY_DETECT_2", num_techs_accelerated)
                    else:
                        co_idx = research_queue_list.index("CON_ORBITAL_CON")
                        res = fo.issueEnqueueTechOrder("SPY_DETECT_2", co_idx + 1)
                    msg = "Empire has poor colony/outpost prospects, so attempted to fast-track %s, got result %d" % ("CON_ORBITAL_CON", res)
                    if report_adjustments:
                        chat_human(msg)
                    else:
                        print msg
                research_queue_list = get_research_queue_techs()

    #
    # check to accelerate xeno_arch
    if True:  # just to help with cold-folding /  organization
        if (ColonisationAI.gotRuins and not tech_is_complete("LRN_XENOARCH") and
                foAI.foAIstate.aggression >= fo.aggression.typical):
            if artif_minds in research_queue_list:
                insert_idx = 7 + research_queue_list.index(artif_minds)
            elif "GRO_SYMBIOTIC_BIO" in research_queue_list:
                insert_idx = research_queue_list.index("GRO_SYMBIOTIC_BIO") + 1
            else:
                insert_idx = num_techs_accelerated
            if "LRN_XENOARCH" not in research_queue_list[:insert_idx]:
                for xenoTech in ["LRN_XENOARCH", "LRN_TRANSLING_THT", "LRN_PHYS_BRAIN", "LRN_ALGO_ELEGANCE"]:
                    if not tech_is_complete(xenoTech) and xenoTech not in research_queue_list[:(insert_idx + 4)]:
                        res = fo.issueEnqueueTechOrder(xenoTech, insert_idx)
                        num_techs_accelerated += 1
                        msg = "ANCIENT_RUINS: have an ancient ruins, so attempted to fast-track %s to enable LRN_XENOARCH, got result %d" % (xenoTech, res)
                        if report_adjustments:
                            chat_human(msg)
                        else:
                            print msg
                research_queue_list = get_research_queue_techs()

    if False and not enemies_sighted:  # curently disabled
        # params = [ (tech, gate, target_slot, add_tech_list), ]
        params = [("GRO_XENO_GENETICS", "PRO_EXOBOTS", "PRO_EXOBOTS", ["GRO_GENETIC_MED", "GRO_XENO_GENETICS"]),
                  ("PRO_EXOBOTS", "PRO_SENTIENT_AUTOMATION", "PRO_SENTIENT_AUTOMATION", ["PRO_EXOBOTS"]),
                  ("PRO_SENTIENT_AUTOMATION", "PRO_NANOTECH_PROD", "PRO_NANOTECH_PROD", ["PRO_SENTIENT_AUTOMATION"]),
                  ("PRO_INDUSTRY_CENTER_I", "GRO_SYMBIOTIC_BIO", "GRO_SYMBIOTIC_BIO", ["PRO_ROBOTIC_PROD", "PRO_FUSION_GEN", "PRO_INDUSTRY_CENTER_I"]),
                  ("GRO_SYMBIOTIC_BIO", "SHP_ORG_HULL", "SHP_ZORTRIUM_PLATE", ["GRO_SYMBIOTIC_BIO"]),
                  ]
        for (tech, gate, target_slot, add_tech_list) in params:
            if tech_is_complete(tech):
                break
            if tech_turns_left.get(gate, 0) not in [0, 1, 2]:  # needs to exclude -1, the flag for no predicted completion
                continue
            if target_slot in research_queue_list:
                target_index = 1 + research_queue_list.index(target_slot)
            else:
                target_index = num_techs_accelerated
            for move_tech in add_tech_list:
                print "for tech %s, target_slot %s, target_index:%s ; num_techs_accelerated:%s" % (move_tech, target_slot, target_index, num_techs_accelerated)
                if tech_is_complete(move_tech):
                    continue
                if target_index <= num_techs_accelerated:
                    num_techs_accelerated += 1
                if move_tech not in research_queue_list[:1 + target_index]:
                    res = fo.issueEnqueueTechOrder(move_tech, target_index)
                    msg = "Research: To prioritize %s, have advanced %s to slot %d" % (tech, move_tech, target_index)
                    if report_adjustments:
                        chat_human(msg)
                    else:
                        print msg
                    target_index += 1
    #
    # check to accelerate asteroid or GG tech
    if True:  # just to help with cold-folding / organization
        if ColonisationAI.got_ast:
            insert_idx = num_techs_accelerated if "GRO_SYMBIOTIC_BIO" not in research_queue_list else research_queue_list.index("GRO_SYMBIOTIC_BIO")
            ast_tech = "PRO_MICROGRAV_MAN"
            if not (tech_is_complete(ast_tech) or ast_tech in research_queue_list[:(1 + insert_idx)]):
                res = fo.issueEnqueueTechOrder(ast_tech, insert_idx)
                num_techs_accelerated += 1
                msg = "Asteroids: plan to colonize an asteroid belt, so attempted to fast-track %s , got result %d" % (ast_tech, res)
                if report_adjustments:
                    chat_human(msg)
                else:
                    print msg
                research_queue_list = get_research_queue_techs()
            elif tech_is_complete("SHP_ZORTRIUM_PLATE"):
                insert_idx = (1 + insert_idx) if "LRN_FORCE_FIELD" not in research_queue_list else max(1 + insert_idx, research_queue_list.index("LRN_FORCE_FIELD") - 1)
                for ast_tech in ["SHP_ASTEROID_HULLS", "SHP_IMPROVED_ENGINE_COUPLINGS"]:
                    if not tech_is_complete(ast_tech) and ast_tech not in research_queue_list[:insert_idx + 1]:
                        res = fo.issueEnqueueTechOrder(ast_tech, insert_idx)
                        num_techs_accelerated += 1
                        insert_idx += 1
                        msg = "Asteroids: plan to colonize an asteroid belt, so attempted to fast-track %s , got result %d" % (ast_tech, res)
                        print msg
                        if report_adjustments:
                            chat_human(msg)
                research_queue_list = get_research_queue_techs()
        if ColonisationAI.got_gg and not tech_is_complete("PRO_ORBITAL_GEN"):
            fusion_idx = 0 if "PRO_FUSION_GEN" not in research_queue_list else (1 + research_queue_list.index("PRO_FUSION_GEN"))
            forcefields_idx = 0 if "LRN_FORCE_FIELD" not in research_queue_list else (1 + research_queue_list.index("LRN_FORCE_FIELD"))
            insert_idx = max(fusion_idx, forcefields_idx) if enemies_sighted else fusion_idx
            if "PRO_ORBITAL_GEN" not in research_queue_list[:insert_idx+1]:
                res = fo.issueEnqueueTechOrder("PRO_ORBITAL_GEN", insert_idx)
                num_techs_accelerated += 1
                msg = "GasGiant: plan to colonize a gas giant, so attempted to fast-track %s, got result %d" % ("PRO_ORBITAL_GEN", res)
                print msg
                if report_adjustments:
                    chat_human(msg)
                research_queue_list = get_research_queue_techs()
    #
    # assess if our empire has any non-lousy colonizers, & boost gro_xeno_gen if we don't
    if True:  # just to help with cold-folding / organization
        if got_ggg_tech and got_sym_bio and (not got_xeno_gen) and foAI.foAIstate.aggression >= fo.aggression.cautious:
            most_adequate = 0
            for specName in ColonisationAI.empire_colonizers:
                environs = {}
                this_spec = fo.getSpecies(specName)
                if not this_spec:
                    continue
                for ptype in [fo.planetType.swamp, fo.planetType.radiated, fo.planetType.toxic, fo.planetType.inferno, fo.planetType.barren, fo.planetType.tundra, fo.planetType.desert, fo.planetType.terran, fo.planetType.ocean, fo.planetType.asteroids]:
                    environ = this_spec.getPlanetEnvironment(ptype)
                    environs.setdefault(environ, []).append(ptype)
                most_adequate = max(most_adequate, len(environs.get(fo.planetEnvironment.adequate, [])))
            if most_adequate == 0:
                insert_idx = num_techs_accelerated
                for xg_tech in ["GRO_XENO_GENETICS", "GRO_GENETIC_ENG"]:
                    if xg_tech not in research_queue_list[:1+num_techs_accelerated] and not tech_is_complete(xg_tech):
                        res = fo.issueEnqueueTechOrder(xg_tech, insert_idx)
                        num_techs_accelerated += 1
                        msg = "Empire has poor colonizers, so attempted to fast-track %s, got result %d" % (xg_tech, res)
                        print msg
                        if report_adjustments:
                            chat_human(msg)
                research_queue_list = get_research_queue_techs()
    #
    # check to accelerate distrib thought
    if True:  # just to help with cold-folding / organization
        if not tech_is_complete("LRN_DISTRIB_THOUGHT"):
            got_telepathy = False
            for specName in ColonisationAI.empire_species:
                this_spec = fo.getSpecies(specName)
                if this_spec and ("TELEPATHIC" in list(this_spec.tags)):
                    got_telepathy = True
                    break
            if (foAI.foAIstate.aggression > fo.aggression.cautious) and (empire.population() > ([300, 100][got_telepathy])):
                insert_idx = num_techs_accelerated
                for dt_ech in ["LRN_PHYS_BRAIN", "LRN_TRANSLING_THT", "LRN_PSIONICS", "LRN_DISTRIB_THOUGHT"]:
                    if dt_ech not in research_queue_list[:insert_idx + 2] and not tech_is_complete(dt_ech):
                        res = fo.issueEnqueueTechOrder(dt_ech, insert_idx)
                        num_techs_accelerated += 1
                        insert_idx += 1
                        fmt_str = "Empire has a telepathic race, so attempted to fast-track %s (got result %d)"
                        fmt_str += " with current target_RP %.1f and current pop %.1f, on turn %d"
                        msg = fmt_str % (dt_ech, res, resource_production, empire.population(), fo.currentTurn())
                        print msg
                        if report_adjustments:
                            chat_human(msg)
                research_queue_list = get_research_queue_techs()
    #
    # check to accelerate quant net
    if False:  # disabled for now, otherwise just to help with cold-folding / organization
        if (foAI.foAIstate.aggression > fo.aggression.cautious) and (ColonisationAI.empire_status.get('researchers', 0) >= 40):
            if not tech_is_complete("LRN_QUANT_NET"):
                insert_idx = num_techs_accelerated  # TODO determine min target slot if reenabling
                for qnTech in ["LRN_NDIM_SUBSPACE", "LRN_QUANT_NET"]:
                    if qnTech not in research_queue_list[:insert_idx + 2] and not tech_is_complete(qnTech):
                        res = fo.issueEnqueueTechOrder(qnTech, insert_idx)
                        num_techs_accelerated += 1
                        insert_idx += 1
                        msg = "Empire has many researchers, so attempted to fast-track %s (got result %d) on turn %d" % (qnTech, res, fo.currentTurn())
                        print msg
                        if report_adjustments:
                            chat_human(msg)
                research_queue_list = get_research_queue_techs()

    #
    # if we own a blackhole, accelerate sing_gen and conc camp
    if True:  # just to help with cold-folding / organization
        if (fo.currentTurn() > 50 and len(AIstate.empireStars.get(fo.starType.blackHole, [])) != 0 and
                foAI.foAIstate.aggression > fo.aggression.cautious and not tech_is_complete(AIDependencies.PRO_SINGULAR_GEN) and
                tech_is_complete(AIDependencies.PRO_SOL_ORB_GEN)):
            # sing_tech_list = [ "LRN_GRAVITONICS" , "PRO_SINGULAR_GEN"]  # formerly also "CON_ARCH_PSYCH", "CON_CONC_CAMP",
            sing_gen_tech = fo.getTech(AIDependencies.PRO_SINGULAR_GEN)
            sing_tech_list = [pre_req for pre_req in sing_gen_tech.recursivePrerequisites(empire_id) if not tech_is_complete(pre_req)]
            sing_tech_list += [AIDependencies.PRO_SINGULAR_GEN]
            for singTech in sing_tech_list:
                if singTech not in research_queue_list[:num_techs_accelerated+1]:
                    res = fo.issueEnqueueTechOrder(singTech, num_techs_accelerated)
                    num_techs_accelerated += 1
                    msg = "have a black hole star outpost/colony, so attempted to fast-track %s, got result %d" % (singTech, res)
                    print msg
                    if report_adjustments:
                        chat_human(msg)
            research_queue_list = get_research_queue_techs()

    #
    # if got deathray from Ruins, remove most prereqs from queue
    if True:  # just to help with cold-folding / organization
        if tech_is_complete("SHP_WEAPON_4_1"):
            this_tech = fo.getTech("SHP_WEAPON_4_1")
            if this_tech:
                missing_prereqs = [preReq for preReq in this_tech.recursivePrerequisites(empire_id) if preReq in research_queue_list]
                if len(missing_prereqs) > 2:  # leave plasma 4 and 3 if up to them already
                    for preReq in missing_prereqs:  # sorted(missing_prereqs, reverse=True)[2:]
                        if preReq in research_queue_list:
                            fo.issueDequeueTechOrder(preReq)
                    research_queue_list = get_research_queue_techs()
                    if "SHP_WEAPON_4_2" in research_queue_list:  # (should be)
                        idx = research_queue_list.index("SHP_WEAPON_4_2")
                        fo.issueEnqueueTechOrder("SHP_WEAPON_4_2", max(0, idx-18))

    # TODO: Remove the following example code
    # Example/Test code for the new ShipDesigner functionality
    techs = ["SHP_WEAPON_4_2", "SHP_TRANSSPACE_DRIVE", "SHP_INTSTEL_LOG", "SHP_ASTEROID_HULLS", ""]
    for tech in techs:
        this_tech = fo.getTech(tech)
        if not this_tech:
            print "Invalid Tech specified"
            continue
        unlocked_items = this_tech.unlockedItems
        unlocked_hulls = []
        unlocked_parts = []
        for item in unlocked_items:
            if item.type == fo.unlockableItemType.shipPart:
                print "Tech %s unlocks a ShipPart: %s" % (tech, item.name)
                unlocked_parts.append(item.name)
            elif item.type == fo.unlockableItemType.shipHull:
                print "Tech %s unlocks a ShipHull: %s" % (tech, item.name)
                unlocked_hulls.append(item.name)
        if not (unlocked_parts or unlocked_hulls):
            print "No new ship parts/hulls unlocked by tech %s" % tech
            continue
        old_designs = ShipDesignAI.MilitaryShipDesigner().optimize_design(consider_fleet_count=False)
        new_designs = ShipDesignAI.MilitaryShipDesigner().optimize_design(additional_hulls=unlocked_hulls, additional_parts=unlocked_parts, consider_fleet_count=False)
        if not (old_designs and new_designs):
            # AI is likely defeated; don't bother with logging error message
            continue
        old_rating, old_pid, old_design_id, old_cost = old_designs[0]
        old_design = fo.getShipDesign(old_design_id)
        new_rating, new_pid, new_design_id, new_cost = new_designs[0]
        new_design = fo.getShipDesign(new_design_id)
        if new_rating > old_rating:
            print "Tech %s gives access to a better design!" % tech
            print "old best design: Rating %.5f" % old_rating
            print "old design specs: %s - " % old_design.hull, list(old_design.parts)
            print "new best design: Rating %.5f" % new_rating
            print "new design specs: %s - " % new_design.hull, list(new_design.parts)
        else:
            print "Tech %s gives access to new parts or hulls but there seems to be no military advantage." % tech

def use_classic_research_approach():
    # TODO: make research approach dependent on AI Config
    return True


def generate_research_orders():
    """generate research orders"""

    if use_classic_research_approach():
        generate_classic_research_orders()
        return
    
    # initializing priority functions here within generate_research_orders() to avoid import race

    DEFENSIVE = foAI.foAIstate.aggression <= fo.aggression.cautious

    # keys are "PREFIX1", as in "DEF" or "SPY"
    if not primary_prefix_priority_funcs:
        primary_prefix_priority_funcs.update({
            AIDependencies.DEFENSE_TECHS_PREFIX: partial(const_priority, 2.0) if DEFENSIVE else partial(if_enemies, 0.2)
            })

    # keys are "PREFIX1_PREFIX2", as in "SHP_WEAPON"
    if not secondary_prefix_priority_funcs:
        secondary_prefix_priority_funcs.update({
            AIDependencies.WEAPON_PREFIX: partial(ship_usefulness, partial(if_enemies, 0.2), MIL_IDX)
            })

    if not priority_funcs:
        tech_handlers = (
            (
                AIDependencies.PRO_MICROGRAV_MAN,
                partial(conditional_priority, partial(const_priority, 3.5), priority_low, None, ColonisationAI,
                        'got_ast')
            ),
            (
                AIDependencies.PRO_ORBITAL_GEN,
                partial(conditional_priority, partial(const_priority, 3.0), priority_low, None, ColonisationAI,
                        'got_gg')
            ),
            (
                AIDependencies.PRO_SINGULAR_GEN,
                partial(conditional_priority,
                        partial(const_priority, 3.0),
                        priority_low, partial(has_star,
                                              fo.starType.blackHole))
            ),
            (
                AIDependencies.GRO_XENO_GENETICS,
                get_xeno_genetics_priority
            ),
            (
                AIDependencies.LRN_XENOARCH,
                priority_low if foAI.foAIstate.aggression < fo.aggression.typical else partial(
                    conditional_priority,
                    partial(const_priority, 5.0),
                    priority_low, None,
                    ColonisationAI, 'gotRuins')
            ),
            (
                AIDependencies.LRN_ART_BLACK_HOLE,
                get_artificial_black_hole_priority),
            (
                (AIDependencies.GRO_GENOME_BANK,), priority_low
            ),
            (
                AIDependencies.CON_CONC_CAMP,
                partial(priority_zero)
            ),
            (
                AIDependencies.NEST_DOMESTICATION_TECH,
                priority_zero if foAI.foAIstate.aggression < fo.aggression.typical else partial(
                    conditional_priority,
                    partial(const_priority, 3.0),
                    priority_low, None, ColonisationAI,
                    'got_nest')
            ),
            (
                AIDependencies.UNRESEARCHABLE_TECHS,
                partial(const_priority, -1.0)
            ),
            (
                AIDependencies.UNUSED_TECHS,
                priority_zero
            ),
            (
                AIDependencies.THEORY_TECHS,
                priority_zero
            ),
            (
                AIDependencies.PRODUCTION_BOOST_TECHS,
                partial(if_dict, ColonisationAI.empire_status,
                        'industrialists', 0.6, 1.5)
            ),
            (
                AIDependencies.RESEARCH_BOOST_TECHS,
                partial(if_tech_target, get_initial_research_target(), 2.1, 2.5)
            ),
            (
                AIDependencies.PRODUCTION_AND_RESEARCH_BOOST_TECHS,
                partial(const_priority, 2.5)
            ),
            (
                AIDependencies.POPULATION_BOOST_TECHS,
                get_population_boost_priority
            ),
            (
                AIDependencies.SUPPLY_BOOST_TECHS,
                partial(if_tech_target, AIDependencies.SUPPLY_BOOST_TECHS[0], 1.0, 0.5)
            ),
            (
                AIDependencies.METER_CHANGE_BOOST_TECHS,
                partial(const_priority, 1.0)
            ),
            (
                AIDependencies.DETECTION_TECHS,
                partial(const_priority, 0.5)
            ),
            (
                AIDependencies.STEALTH_TECHS,
                get_stealth_priority
            ),
            (
                AIDependencies.DAMAGE_CONTROL_TECHS,
                partial(if_enemies, 0.1, 0.5)
            ),
            (
                AIDependencies.HULL_TECHS,
                get_hull_priority
            ),
            (
                AIDependencies.ARMOR_TECHS,
                partial(ship_usefulness, if_enemies, MIL_IDX)
            ),
            (
                AIDependencies.ENGINE_TECHS,
                partial(ship_usefulness, partial(if_dict, choices, 'engine', true_val=0.6), None)
            ),
            (
                AIDependencies.FUEL_TECHS,
                partial(ship_usefulness, partial(if_dict, choices, 'fuel'), None)),
            (
                AIDependencies.SHIELD_TECHS,
                partial(ship_usefulness, if_enemies, MIL_IDX)
            ),
            (
                AIDependencies.TROOP_POD_TECHS,
                partial(ship_usefulness,
                        partial(if_enemies, 0.1, 0.3), TROOP_IDX)
            ),
            (
                AIDependencies.COLONY_POD_TECHS,
                partial(ship_usefulness, partial(const_priority, 0.5), COLONY_IDX)
            ),
        )
        for k, v in tech_handlers:
            if isinstance(k, basestring):
                k = (k, )  # wrap single techs to tuple
            for tech in k:
                priority_funcs[tech] = v

    empire = fo.getEmpire()
    empire_id = empire.empireID
    print "Research Queue Management on turn %d:" % fo.currentTurn()
    print "ColonisationAI survey: got_ast %s, got_gg %s, gotRuins %s" % (ColonisationAI.got_ast, ColonisationAI.got_gg, ColonisationAI.gotRuins)
    resource_production = empire.resourceProduction(fo.resourceType.research)
    print "\nTotal Current Research Points: %.2f\n" % resource_production
    print "Techs researched and available for use:"
    completed_techs = sorted(list(get_completed_techs()))
    tlist = completed_techs+3*[" "]
    tlines = zip(tlist[0::3], tlist[1::3], tlist[2::3])
    for tline in tlines:
        print "%25s %25s %25s" % tline
    print

    #
    # report techs currently at head of research queue
    #
    research_queue = empire.researchQueue
    research_queue_list = get_research_queue_techs()
    tech_turns_left = {}
    if research_queue_list:
        print "Techs currently at head of Research Queue:"
        for element in list(research_queue)[:10]:
            tech_turns_left[element.tech] = element.turnsLeft
            this_tech = fo.getTech(element.tech)
            if not this_tech:
                print "Error: can't retrieve tech ", element.tech
                continue
            missing_prereqs = [preReq for preReq in this_tech.recursivePrerequisites(empire_id) if preReq not in completed_techs]
            # unlocked_items = [(uli.name, uli.type) for uli in this_tech.unlocked_items]
            unlocked_items = [uli.name for uli in this_tech.unlockedItems]
            if not missing_prereqs:
                print "    %25s allocated %6.2f RP -- unlockable items: %s " % (element.tech, element.allocation, unlocked_items)
            else:
                print "    %25s allocated %6.2f RP -- missing preReqs: %s -- unlockable items: %s " % (element.tech, element.allocation, missing_prereqs, unlocked_items)
        print

    #
    # calculate all research priorities, as in get_priority(tech) / total cost of tech (including prereqs)
    #
    rng = random.Random()
    rng.seed(fo.getEmpire().name + fo.getGalaxySetupData().seed)

    if '_selected' not in choices:
        choices['_selected'] = True
        choices['engine'] = rng.random() < 0.7
        choices['fuel'] = rng.random() < 0.7
        
        choices['hull'] = rng.randrange(4)
        choices['extra_organic_hull'] = rng.random() < 0.05
        choices['extra_robotic_hull'] = rng.random() < 0.05
        choices['extra_asteroid_hull'] = rng.random() < 0.05
        choices['extra_energy_hull'] = rng.random() < 0.05

    calculate_research_requirements()
    total_rp = empire.resourceProduction(fo.resourceType.research)

    if total_rp <= 0:  # No RP available - no research.
        return

    base_priorities = {}
    priorities = {}
    on_path_to = {}
    for tech_name in fo.techs():
        this_tech = fo.getTech(tech_name)
        if not this_tech or tech_is_complete(tech_name):
            continue
        base_priorities[tech_name] = priorities[tech_name] = get_priority(tech_name)

    # inherited priorities are modestly attenuated by total time
    TIMESCALE_PERIOD = 30.0
    for tech_name, priority in base_priorities.iteritems():
        if priority >= 0:
            turns_needed = max(research_reqs[tech_name][REQS_TIME_IDX], math.ceil(float(research_reqs[tech_name][REQS_COST_IDX]) / total_rp))
            time_attenuation = 2**(-max(0.0, turns_needed-5)/TIMESCALE_PERIOD)
            attenuated_priority = priority * time_attenuation
            for prereq in research_reqs.get(tech_name, ([], 0, 0, 0))[REQS_PREREQS_IDX]:
                if prereq in priorities and attenuated_priority > priorities[prereq]:  # checking like this to keep finished techs out of priorities
                    priorities[prereq] = attenuated_priority
                    on_path_to[prereq] = tech_name

    # final priorities are scaled by a combination of relative per-turn cost and relative total cost
    for tech_name, priority in priorities.iteritems():
        if priority >= 0:
            relative_turn_cost = max(research_reqs[tech_name][REQS_PER_TURN_COST_IDX], 0.1) / total_rp
            relative_total_cost = max(research_reqs[tech_name][REQS_COST_IDX], 0.1) / total_rp
            cost_factor = 2.0 / (relative_turn_cost + relative_total_cost)
            adjusted_priority = float(priority) * cost_factor
            # if priority > 1:
            #    print "tech %s has raw priority %.1f and adjusted priority %.1f, with %.1f total remaining cost, %.1f min turns needed and %.1f projected turns needed" % (tech_name, priority, adjusted_priority, research_reqs[tech_name][REQS_COST_IDX], research_reqs[tech_name][REQS_TIME_IDX], turns_needed)
            priorities[tech_name] = adjusted_priority

    #
    # put in highest priority techs until all RP spent, with  time then cost as minor sorting keys
    #
    possible = sorted(priorities.keys(), key=tech_cost_sort_key)
    possible.sort(key=tech_time_sort_key)
    possible.sort(key=priorities.__getitem__, reverse=True)

    missing_prereq_list = []
    print "Research priorities"
    print "    %25s %8s %8s %8s %25s %s" % ("Name", "Priority", "Cost", "Time", "As Prereq To", "Missing Prerequisties")
    for idx, tech_name in enumerate(possible[:20]):
        tech_info = research_reqs[tech_name]
        print "    %25s %8.6f %8.2f %8.2f %25s %s" % (tech_name, priorities[tech_name], tech_info[1], tech_info[2], on_path_to.get(tech_name, ""), tech_info[0])
        missing_prereq_list.extend([prereq for prereq in tech_info[0] if prereq not in possible[:idx] and not tech_is_complete(prereq)])
    print

    print "Prereqs seeming out of order:"
    print "    %25s %8s %8s %8s %8s %25s %s" % ("Name", "Priority", "Base Prio",  "Cost", "Time", "As Prereq To", "Missing Prerequisties")
    for tech_name in missing_prereq_list:
        tech_info = research_reqs[tech_name]
        print "    %25s %8.6f %8.6f %8.2f %8.2f %25s %s" % (tech_name, priorities[tech_name], base_priorities[tech_name], tech_info[1], tech_info[2], on_path_to.get(tech_name, ""), tech_info[0])


    print "enqueuing techs. already spent RP: %s total RP: %s" % (fo.getEmpire().researchQueue.totalSpent, total_rp)

    if fo.currentTurn() == 1 and not research_queue_list:
        fo.issueEnqueueTechOrder("GRO_PLANET_ECOL", -1)
        fo.issueEnqueueTechOrder("LRN_ALGO_ELEGANCE", -1)
    else:
        # some floating point issues can cause AI to enqueue every tech......
        queued_techs = set(get_research_queue_techs())
        while empire.resourceProduction(fo.resourceType.research) - empire.researchQueue.totalSpent > 0.001 and possible:
            to_research = possible.pop(0)  # get tech with highest priority
            if to_research not in queued_techs:
                fo.issueEnqueueTechOrder(to_research, -1)
                queued_techs.add(to_research)
                print "    enqueued tech " + to_research + "  : cost: " + str(fo.getTech(to_research).researchCost(empire.empireID)) + "RP"
                fo.updateResearchQueue()
        print



def generate_default_research_order():
    """
    Generate default research orders.
    Add cheapest technology from possible researches
    until current turn point totally spent.
    """

    empire = fo.getEmpire()
    total_rp = empire.resourceProduction(fo.resourceType.research)

    # get all usable researchable techs not already completed or queued for research

    queued_techs = get_research_queue_techs()

    def is_possible(tech_name):
        return all([empire.getTechStatus(tech_name) == fo.techStatus.researchable,
                   not tech_is_complete(tech_name),
                   not exclude_tech(tech_name),
                   tech_name not in queued_techs])

    # (cost, name) for all tech that possible to add to queue, cheapest last
    possible = sorted(
        [(fo.getTech(tech).researchCost(empire.empireID), tech) for tech in fo.techs() if is_possible(tech)],
        reverse=True)

    print "Techs in possible list after enqueues to Research Queue:"
    for _, tech in possible:
        print "    " + tech
    print

    # iterate through techs in order of cost
    fo.updateResearchQueue()
    total_spent = fo.getEmpire().researchQueue.totalSpent
    print "enqueuing techs. already spent RP: %s total RP: %s" % (total_spent, total_rp)

    while total_rp > 0 and possible:
        cost, name = possible.pop()  # get chipest
        total_rp -= cost
        fo.issueEnqueueTechOrder(name, -1)
        print "    enqueued tech " + name + "  : cost: " + str(cost) + "RP"
    print


def get_possible_projects():
    """get possible projects"""
    preliminary_projects = []
    empire = fo.getEmpire()
    for tech_name in fo.techs():
        if empire.getTechStatus(tech_name) == fo.techStatus.researchable:
            preliminary_projects.append(tech_name)
    return set(preliminary_projects)-set(TechsListsAI.unusable_techs())


def get_completed_techs():
    """get completed and available for use techs"""
    return [tech for tech in fo.techs() if tech_is_complete(tech)]


def get_research_queue_techs():
    """ Get list of techs in research queue."""
    return [element.tech for element in fo.getEmpire().researchQueue]

def exclude_tech(tech_name):
    return ((foAI.foAIstate.aggression < AIDependencies.TECH_EXCLUSION_MAP_1.get(tech_name, fo.aggression.invalid)) or
            (foAI.foAIstate.aggression > AIDependencies.TECH_EXCLUSION_MAP_2.get(tech_name, fo.aggression.maniacal)) or
            tech_name in TechsListsAI.unusable_techs())


