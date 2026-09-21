"""The decision boundary. Swappable: the engine only ever calls
Policy.decide(text, available) -- it neither knows nor cares what's behind it.

The policy sees ONLY the plain-text banded state and the list of legal action
names. It never sees raw numbers, positions, or outcome odds (DESIGN.md: "Jev
never sees the odds -- that's the point").
"""

import json
import os
import pathlib
import random
import threading
import time
import urllib.request

from . import config as C


class Policy:
    parallel = False  # engine may fan out decide() across threads when True

    def decide(self, perceived_state_text: str, available_actions: list) -> str:
        """Return one action name from available_actions."""
        return self.decide_verbose(perceived_state_text, available_actions)["action"]

    def decide_verbose(self, perceived_state_text: str, available_actions: list) -> dict:
        """Full decision detail: {action, choice, confidence, probabilities,
        state_text, available}. decide() is derived from this; subclasses that
        override decide() directly must still implement this for the live view."""
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

        if "flee" in available_actions:
            if threat == "predator closing" and not (starving and stamina == "spent"):
                return "flee"
            if threat == "predator nearby" and health in ("injured", "hurt"):
                return "flee"

        if cur_action == "hunt" and stamina in ("spent", "winded"):
            if "fleeing" in prey or cur_dur == "dragging on":
                return "rest"

        if thirst == "parched" and "drink" in available_actions:
            return "drink"
        if (thirst == "thirsty" and "drink" in available_actions
                and threat == "none" and not starving):
            return "drink"

        if species == "jackal" and "eat" in available_actions and hunger != "full":
            return "eat"
        if (species == "lion" and "hunt" in available_actions
                and prey == "in range" and hunger != "full"):
            return "hunt"
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
                if "hunt" in available_actions:
                    return "hunt"
                if "eat" in available_actions:
                    return "eat"

        if cur_action in ("drink", "eat", "graze") and cur_action in available_actions:
            if cur_action == "drink" and thirst != "fine":
                return "drink"
            if cur_action in ("eat", "graze") and hunger != "full":
                return cur_action

        if stamina == "spent":
            return "rest"
        if health in ("injured", "hurt") and threat == "none":
            return "rest"
        if "mate" in available_actions:
            return "mate"

        if hunger in ("satisfied", "full") and threat == "none" and thirst == "fine":
            if carcass in ("at hand", "close"):
                return "rest"
            return "rest" if self.rng.random() < 0.7 else "wander"
        return "wander"

    def decide_verbose(self, perceived_state_text: str, available_actions: list) -> dict:
        action = self.decide(perceived_state_text, available_actions)
        return {
            "action": action,
            "choice": action,
            "confidence": 1.0,
            "probabilities": {a: (1.0 if a == action else 0.0)
                              for a in available_actions} or None,
            "state_text": perceived_state_text,
            "available": list(available_actions),
        }


# One-line descriptions sent to Jev as the Choice options. Clear descriptions
# matter: Jev sees the option name AND this text, nothing else.
ACTION_DESCRIPTIONS = {
    "hunt": "Chase and attack the nearest prey animal you can see",
    "flee": "Run away from the predator that is threatening you",
    "eat": "Feed on the carcass you have found",
    "graze": "Eat the vegetation you can see",
    "drink": "Head to water and drink",
    "rest": "Stay still to recover stamina and heal",
    "mate": "Go to a nearby mate and breed",
    "wander": "Roam to search for food, water, or a mate",
}


class JevMetrics:
    """Thread-safe running metrics for Jev API calls."""

    def __init__(self):
        self._lock = threading.Lock()
        self.requests = 0
        self.errors = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.total_latency_ms = 0.0
        self.confidence_sum = 0.0
        self.first_ts = None
        self.last_ts = None

    def record(self, latency_ms, in_tok, out_tok, conf):
        with self._lock:
            self.requests += 1
            self.total_latency_ms += latency_ms
            self.input_tokens += in_tok
            self.output_tokens += out_tok
            self.confidence_sum += conf
            now = time.time()
            if self.first_ts is None:
                self.first_ts = now
            self.last_ts = now

    def record_error(self):
        with self._lock:
            self.errors += 1

    def snapshot(self):
        with self._lock:
            reqs = self.requests
            elapsed = 0.0
            if self.first_ts and self.last_ts and self.last_ts > self.first_ts:
                elapsed = self.last_ts - self.first_ts
            in_tok, out_tok = self.input_tokens, self.output_tokens
            cost = (in_tok / 1e6 * C.JEV_PRICE_PER_1M_INPUT
                    + out_tok / 1e6 * C.JEV_PRICE_PER_1M_OUTPUT)
            return {
                "requests": reqs,
                "errors": self.errors,
                "avg_latency_ms": round(self.total_latency_ms / reqs, 1) if reqs else 0.0,
                "req_per_s": round(reqs / elapsed, 1) if elapsed > 0 else 0.0,
                "input_tokens": in_tok,
                "output_tokens": out_tok,
                "avg_confidence": round(self.confidence_sum / reqs, 3) if reqs else 0.0,
                "est_cost_usd": round(cost, 4),
                "price_known": C.JEV_PRICE_PER_1M_INPUT > 0 or C.JEV_PRICE_PER_1M_OUTPUT > 0,
            }


class JevPolicy(Policy):
    """Asks Jev (typesafe.ai) for the typed decision.

    One Choice question per animal per tick: `state` is the banded plain-text
    perception, the options are the legal action mask. Jev returns the chosen
    action plus a calibrated confidence. On any error it falls back to the
    heuristic so the sim never stalls, and it records that as an error.
    """

    parallel = True

    def __init__(self, api_key=None, endpoint=None, model=None, timeout=None,
                 metrics=None, fallback=None):
        self.api_key = api_key or os.environ.get("TYPESAFE_API_KEY") or self._key_from_config()
        if not self.api_key:
            raise RuntimeError(
                "JevPolicy: no API key (set TYPESAFE_API_KEY or ~/.typesafe/config.json)")
        self.endpoint = endpoint or C.JEV_ENDPOINT
        self.model = model or C.JEV_MODEL
        self.timeout = timeout if timeout is not None else C.JEV_TIMEOUT
        self.metrics = metrics or JevMetrics()
        self.fallback = fallback or MockPolicy()
        self.sample = False  # if True, the engine samples the action from the
        # returned probability distribution instead of taking the top choice

    @staticmethod
    def _key_from_config():
        try:
            p = pathlib.Path.home() / ".typesafe" / "config.json"
            return json.loads(p.read_text())["api_key"]
        except Exception:
            return None

    def decide_verbose(self, perceived_state_text: str, available_actions: list) -> dict:
        if not available_actions:
            return {"action": "rest", "choice": "rest", "confidence": 1.0,
                    "probabilities": None, "state_text": perceived_state_text,
                    "available": []}
        criteria = {a: ACTION_DESCRIPTIONS.get(a, a) for a in available_actions}
        body = json.dumps({
            "state": perceived_state_text,
            "model": self.model,
            "questions": {
                "action": {
                    "type": "choice",
                    "instructions": ("You are a wild animal. Using only what you "
                                     "perceive, choose the single best action to "
                                     "survive and thrive right now."),
                    "criteria": criteria,
                }
            },
        }).encode()
        req = urllib.request.Request(
            self.endpoint, data=body, method="POST",
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"})
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read())
            latency_ms = (time.time() - t0) * 1000.0
            ans = data.get("answers", {}).get("action", {})
            choice = ans.get("choice")
            conf = ans.get("confidence") or 0.0
            probs = ans.get("probabilities")
            usage = data.get("usage", {})
            self.metrics.record(latency_ms,
                                usage.get("input_tokens", 0),
                                usage.get("output_tokens", 0), conf)
            if choice in available_actions:
                action = choice
            else:  # Jev answered off-mask; act on the heuristic but keep Jev's view
                action = self.fallback.decide(perceived_state_text, available_actions)
            return {"action": action, "choice": choice, "confidence": conf,
                    "probabilities": probs, "state_text": perceived_state_text,
                    "available": list(available_actions)}
        except Exception:
            self.metrics.record_error()
            detail = self.fallback.decide_verbose(perceived_state_text, available_actions)
            detail["state_text"] = perceived_state_text
            return detail
