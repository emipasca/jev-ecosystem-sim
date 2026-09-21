"""The decision boundary. Swappable: the engine only ever calls
Policy.decide(text, available) -- it neither knows nor cares what's behind it.

The policy sees ONLY the plain-text banded state and the list of legal action
names. It never sees raw numbers, positions, or outcome odds (DESIGN.md: "Jev
never sees the odds -- that's the point").
"""

import random


class Policy:
    def decide(self, perceived_state_text: str, available_actions: list) -> str:
        """Return one action name from available_actions."""
        raise NotImplementedError


def _parse(text: str) -> dict:
    """The banded state is 'key: value' lines; parse it back into a dict."""
    state = {}
    for line in text.splitlines():
        key, _, value = line.partition(":")
        state[key.strip()] = value.strip()
    return state


class MockPolicy(Policy):
    """A readable survival heuristic standing in for Jev.

    Priority: flee a closing predator > critical thirst > food when hungry
    > thirst > recover > mate > wander. Hunger raises risk tolerance: a
    starving animal ignores a merely-nearby predator and takes the hunt.
    """

    def __init__(self, seed: int = 0):
        self.rng = random.Random(seed)

    def decide(self, perceived_state_text: str, available_actions: list) -> str:
        s = _parse(perceived_state_text)
        species = s.get("species", "")
        hunger = s.get("hunger", "")
        thirst = s.get("thirst", "")
        stamina = s.get("stamina", "")
        health = s.get("health", "")
        threat = s.get("threat", "none")
        prey = s.get("nearest prey", "none")
        carcass = s.get("carcass", "none")
        current = s.get("current action", "idle (just started)")
        cur_action, _, cur_dur = current.partition(" (")
        cur_dur = cur_dur.rstrip(")")
        starving = hunger == "starving"

        # 1. Survival: a closing predator overrides almost everything. A merely
        #    nearby one only spooks the vulnerable -- alert-but-grazing is what
        #    gives stalking predators their window.
        if "flee" in available_actions:
            if threat == "predator closing" and not (starving and stamina == "spent"):
                return "flee"
            if threat == "predator nearby" and health in ("injured", "hurt"):
                return "flee"

        # 2. Give up on a hopeless chase: the quarry has bolted and the legs
        #    are going. Rest and wait for a fresh chance.
        if cur_action == "hunt" and stamina in ("spent", "winded"):
            if "fleeing" in prey or cur_dur == "dragging on":
                return "rest"

        # 3. Thirst beats food: top up before it becomes an emergency (unless
        #    already starving -- then food first).
        if thirst == "parched" and "drink" in available_actions:
            return "drink"
        if (thirst == "thirsty" and "drink" in available_actions
                and threat == "none" and not starving):
            return "drink"

        # 4. Food. Herbivores graze; scavengers prefer a free carcass; hungry
        #    predators hunt (starving ones even at long range -- desperation).
        #    A jackal at a carcass keeps feeding until actually full -- wander
        #    off and the carrion is lost to rot and other mouths.
        if species == "jackal" and "eat" in available_actions and hunger != "full":
            return "eat"
        # An apex predator doesn't pass up prey that has wandered close...
        if (species == "lion" and "hunt" in available_actions
                and prey == "in range" and hunger != "full"):
            return "hunt"
        # ...and it eats its own kill down over several sittings rather than
        # abandoning the larder to the jackals and the rot.
        if (species == "lion" and "eat" in available_actions
                and carcass in ("at hand", "close") and hunger != "full"):
            return "eat"
        if hunger in ("starving", "hungry"):
            if "graze" in available_actions:
                return "graze"
            if species == "jackal":
                if "eat" in available_actions:
                    return "eat"
                if "hunt" in available_actions:
                    return "hunt"
            else:
                # An apex predator hunts what it can see; carrion is the
                # fallback when nothing living is in sight (else it gets
                # outcompeted at every carcass by the jackals).
                if "hunt" in available_actions:
                    return "hunt"
                if "eat" in available_actions:
                    return "eat"

        # 6. Keep a productive action going rather than dithering.
        if cur_action in ("drink", "eat", "graze") and cur_action in available_actions:
            if cur_action == "drink" and thirst != "fine":
                return "drink"
            if cur_action in ("eat", "graze") and hunger != "full":
                return cur_action

        # 7. Recover when tired or hurt and nothing is pressing. Full animals
        #    laze too (a lion sleeps between hunts instead of burning energy).
        if stamina == "spent":
            return "rest"
        if health in ("injured", "hurt") and threat == "none":
            return "rest"
        # 8. Breed when flush.
        if "mate" in available_actions:
            return "mate"

        # 9. Nothing pressing: mostly laze (a lion sleeps off its kill, a herd
        #    settles), drifting off now and then to keep the map alive. A full
        #    animal with meat still at hand guards it instead of drifting.
        if hunger in ("satisfied", "full") and threat == "none" and thirst == "fine":
            if carcass in ("at hand", "close"):
                return "rest"
            return "rest" if self.rng.random() < 0.7 else "wander"
        return "wander"


class JevPolicy(Policy):
    """Drop-in replacement that asks Jev (typesafe.ai) for the typed decision.

    The engine is already shaped for this: `perceived_state_text` is the full
    plain-text banded state (including the animal's own current action and how
    long it has been running), and `available_actions` is the legal action
    mask. Nothing else in the engine needs to change.
    """

    def __init__(self, api_key: str = None, endpoint: str = None):
        self.api_key = api_key
        self.endpoint = endpoint

    def decide(self, perceived_state_text: str, available_actions: list) -> str:
        # TODO(jev): call the TypeSafe Jev API here.
        #   - send `perceived_state_text` as the observation
        #   - send `available_actions` as the typed action set (the mask)
        #   - return the chosen action name; the calibrated confidence can be
        #     logged/used later (e.g. desperation analytics) but the engine
        #     only needs the action.
        raise NotImplementedError("JevPolicy: wire the TypeSafe Jev API call here")
