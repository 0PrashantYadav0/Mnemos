"""The branching storyline for Mnemos, as data.

Every scene is data; the session engine (:mod:`mnemos.game.session`) interprets
gates, choices, and effects. This keeps the design rule from the plan honest:
*every major choice writes a typed edge, and that exact edge is recalled later.*

Effect DSL (each effect is a one-key dict):
  remember:{deed,target,summary,creates_favor?,witnessed_by?}  write to Brain
  flag:"name" / clear_flag:"name"      set/unset a story flag
  item_add:"item:x" / item_remove      inventory
  faction:"faction:x"                  join a faction (member-of edge)
  improve:"npc:x"                      run memify on that NPC (spread rumors)
  forget:{...}                         surgical Brain.forget()
  ending:"A"|"B"|"C"|"D"               end the game
  note:"text"                          append to the quest log

Gate DSL (list; all must hold):
  flag / not_flag / item / not_item / faction / scene_done / not_scene_done
  owes_favor:"npc:x"                   npc owes the player
  trust_gte:["npc:x",0.3] / trust_lte  disposition thresholds
"""
from __future__ import annotations

# min act each NPC's scenes may appear; also which act completes on flags.
ACT_REQUIREMENTS = {
    1: {"done_mira", "done_dorin", "done_voss"},
    2: {"done_sela", "done_faction", "done_crispin"},
    3: {"done_dorinkey", "done_renna", "done_crispin2"},
    4: {"done_gate"},
}

ACT_INTRO = {
    1: "You wake in the back room of The Last Tankard. You remember nothing -- "
       "but the town remembers you. Find your feet in Market Row and the Forge.",
    2: "Word of your deeds is already travelling. Faces you have never met have "
       "opinions. The factions are watching.",
    3: "The reckoning begins. Old debts come due, and an old ally surfaces from "
       "the past you cannot remember.",
    4: "The Archon moves against you, weaponising the town's memory. Reach the "
       "Archive -- past the Watch Gate.",
    5: "The Archive. Everything the town remembers is stored here. Face the "
       "Archon, and let the graph you built decide your fate.",
}


SCENES: dict[str, list[dict]] = {
    # ================= MIRA (Baker) =================
    "npc:mira": [
        {
            "id": "1A", "act": 1, "max_act": 1, "once": True,
            "prompt": "Mira wrings her apron. \"You... I know your face. Listen -- "
                      "a collector wants 10 coins by dusk or my stall is his. "
                      "I'd not ask, but I'm desperate.\"",
            "choices": [
                {"label": "Pay her debt (10 coins)", "icon": "coin",
                 "effects": [
                     {"remember": {"deed": "helped", "target": "npc:mira",
                                   "summary": "the stranger paid Mira's debt",
                                   "creates_favor": True}},
                     {"flag": "paid_mira_debt"}, {"flag": "done_mira"},
                     {"improve": "npc:mira"},
                     {"note": "Mira owes you a favour."}],
                 "result": "\"You... you paid it. Bless you, stranger. I won't "
                           "forget this. Neither will the town.\""},
                {"label": "Demand her mother's ring as collateral", "icon": "harm",
                 "effects": [
                     {"remember": {"deed": "harmed", "target": "npc:mira",
                                   "summary": "the stranger seized Mira's ring"}},
                     {"flag": "harmed_mira"}, {"flag": "done_mira"},
                     {"improve": "npc:mira"},
                     {"note": "Mira thinks you a shark."}],
                 "result": "She slides the ring off, hands shaking. \"They said "
                           "you were cruel. I hoped they were wrong.\""},
                {"label": "Walk away", "icon": "ignore",
                 "effects": [{"flag": "done_mira"},
                             {"remember": {"deed": "distrusts", "target": "npc:mira",
                                           "summary": "the stranger ignored Mira's plea"}}],
                 "result": "You turn. Her silence follows you out."},
            ],
        },
        {
            "id": "3B_warn", "act": 3, "gate": [{"owes_favor": "npc:mira"}],
            "once": True,
            "prompt": "Mira leans close. \"My friends hear things. There's an "
                      "ambush waiting for you near the Archive. Take the side "
                      "door -- I'll tell them to leave it open for you.\"",
            "choices": [
                {"label": "Thank her", "icon": "help",
                 "effects": [{"flag": "mira_side_door"},
                             {"note": "Mira's network opened a side door."}],
                 "result": "\"Go safe. The whole Row is rooting for you now.\""},
            ],
        },
        {
            "id": "3B_betray", "act": 3, "gate": [{"flag": "harmed_mira"}],
            "once": True,
            "prompt": "Mira stares coldly. \"People are asking about you. I told "
                      "them exactly what kind of stranger you are.\"",
            "choices": [
                {"label": "Leave", "icon": "ignore",
                 "effects": [{"flag": "mira_warned_enemies"},
                             {"note": "Mira's gossip network now works against you."}],
                 "result": "Her words will reach the Archive before you do."},
            ],
        },
    ],

    # ================= DORIN (Blacksmith) =================
    "npc:dorin": [
        {
            "id": "1B", "act": 1, "max_act": 1, "once": True,
            "prompt": "Dorin scowls over his anvil. \"A street kid nicked my "
                      "grandfather's tongs. That's them, in your hand. Well?\"",
            "choices": [
                {"label": "Return the tongs", "icon": "help",
                 "effects": [
                     {"remember": {"deed": "helped", "target": "npc:dorin",
                                   "summary": "the stranger returned Dorin's tongs",
                                   "creates_favor": True}},
                     {"flag": "returned_tongs"}, {"flag": "done_dorin"},
                     {"improve": "npc:dorin"},
                     {"note": "Dorin owes you a favour."}],
                 "result": "\"...Huh. Honest, then. I owe you one, stranger.\""},
                {"label": "Keep them (sell for coin)", "icon": "harm",
                 "effects": [
                     {"remember": {"deed": "harmed", "target": "npc:dorin",
                                   "summary": "the stranger kept Dorin's tongs"}},
                     {"item_add": "item:tongs"}, {"flag": "done_dorin"},
                     {"improve": "npc:dorin"}],
                 "result": "\"Thief. I'll remember that -- and so will the Watch.\""},
            ],
        },
        {
            "id": "3A_gift", "act": 3, "gate": [{"owes_favor": "npc:dorin"}],
            "once": True,
            "prompt": "Dorin sets down his hammer. \"You need into the Archive? "
                      "I owe you. Give me an hour -- I'll forge you a key.\"",
            "choices": [
                {"label": "Accept the Archive Key", "icon": "help",
                 "effects": [{"item_add": "item:archive_key"},
                             {"flag": "done_dorinkey"},
                             {"note": "Dorin forged you the Archive Key."}],
                 "result": "He presses a heavy iron key into your palm. \"Go get "
                           "him. Whatever he did to you.\""},
                {"label": "Ask for a Potion ingredient too", "icon": "coin",
                 "effects": [{"item_add": "item:archive_key"},
                             {"item_add": "item:forge_salt"},
                             {"flag": "done_dorinkey"},
                             {"note": "Dorin gave you the key and forge-salt."}],
                 "result": "\"Salt from the quench-trough? Strange, but it's "
                           "yours. And the key. We're square.\""},
            ],
        },
        {
            "id": "3A_refuse", "act": 3, "gate": [{"trust_lte": ["npc:dorin", -0.1]}],
            "once": True,
            "prompt": "Dorin blocks the forge door. \"You? A key? I already told "
                      "the Watch you'd come sniffing. Get out.\"",
            "choices": [
                {"label": "Leave", "icon": "ignore",
                 "effects": [{"flag": "dorin_reported_you"},
                             {"flag": "done_dorinkey"},
                             {"note": "Dorin refused the key and reported you."}],
                 "result": "You'll need another way into the Archive."},
            ],
        },
    ],

    # ================= VOSS (Guard Captain) =================
    "npc:voss": [
        {
            "id": "1C", "act": 1, "max_act": 1, "once": True,
            "prompt": "Capt. Voss pats his belt, frowning. \"My district seal -- "
                      "dropped it in the crowd. You've sharp eyes. Seen it?\"",
            "choices": [
                {"label": "Return the seal", "icon": "help",
                 "effects": [
                     {"remember": {"deed": "helped", "target": "npc:voss",
                                   "summary": "the stranger returned Voss's seal"}},
                     {"flag": "returned_seal"}, {"flag": "done_voss"},
                     {"improve": "npc:voss"}],
                 "result": "\"Honest hands. The Watch remembers its friends, "
                           "stranger.\""},
                {"label": "Pocket the seal", "icon": "harm",
                 "effects": [
                     {"remember": {"deed": "harmed", "target": "npc:voss",
                                   "summary": "the stranger stole Voss's seal"}},
                     {"item_add": "item:district_seal"}, {"flag": "stole_seal"},
                     {"flag": "done_voss"}, {"improve": "npc:voss"},
                     {"note": "You hold the district seal. Voss will not forget."}],
                 "result": "You palm the seal. Somewhere a rumour is already born: "
                           "\"the stranger is a thief.\""},
            ],
        },
        {
            "id": "4B_gate", "act": 4, "once": True,
            "gate": [{"not_flag": "voss_forgiven"}],
            "prompt": "Voss bars the Archive gate. His reaction depends on what "
                      "he remembers of you...",
            "greet": {
                "warm": "\"You returned my seal once. Go on through -- quietly.\"",
                "friendly": "\"You've been fair. I'll look the other way.\"",
                "hostile": "\"THIEF! You stole my seal. Guards -- ARREST HIM!\"",
                "wary": "\"I don't trust you. State your business.\"",
                "neutral": "\"Halt. No one passes the gate without cause.\"",
            },
            "choices": [
                {"label": "[If trusted] Walk through", "icon": "help",
                 "gate": [{"trust_gte": ["npc:voss", 0.1]}],
                 "effects": [{"flag": "passed_gate"}, {"flag": "done_gate"},
                             {"note": "Voss waved you through the gate."}],
                 "result": "He steps aside. The Archive doors loom ahead."},
                {"label": "[If you have the Archive Key] Unlock it yourself",
                 "icon": "help", "gate": [{"item": "item:archive_key"}],
                 "effects": [{"flag": "passed_gate"}, {"flag": "done_gate"},
                             {"note": "Dorin's key opened the Archive."}],
                 "result": "Dorin's iron key turns. The gate swings wide."},
                {"label": "[If you kept the seal] Forge entry with the seal",
                 "icon": "harm", "gate": [{"item": "item:district_seal"}],
                 "effects": [{"flag": "passed_gate"}, {"flag": "done_gate"},
                             {"flag": "forged_entry"},
                             {"remember": {"deed": "harmed", "target": "npc:voss",
                                           "summary": "the stranger forged entry with the seal"}},
                             {"improve": "npc:voss"},
                             {"note": "You forged entry -- it left evidence."}],
                 "result": "The stolen seal opens the lock. A rumour spreads in "
                           "your wake."},
                {"label": "[If Mira opened it] Take the side door", "icon": "help",
                 "gate": [{"flag": "mira_side_door"}],
                 "effects": [{"flag": "passed_gate"}, {"flag": "done_gate"},
                             {"note": "Mira's side door let you slip past Voss."}],
                 "result": "You slip through the door Mira left open. In you go."},
            ],
        },
        {
            "id": "4A_forget_done", "act": 4,
            "gate": [{"flag": "voss_forgiven"}, {"not_flag": "passed_gate"}],
            "once": True,
            "prompt": "Voss blinks slowly, the grudge gone from his eyes. "
                      "\"...Do I know you? No matter. The gate's open, friend.\"",
            "choices": [
                {"label": "Step through", "icon": "help",
                 "effects": [{"flag": "passed_gate"}, {"flag": "done_gate"},
                             {"note": "The Memory Potion cleared Voss's grudge."}],
                 "result": "He waves you past as if you'd never wronged him."},
            ],
        },
    ],

    # ================= SELA (Healer) =================
    "npc:sela": [
        {
            "id": "2A_good", "act": 2, "max_act": 3, "once": True,
            "gate": [{"trust_gte": ["npc:sela", 0.05]}],
            "prompt": "Sela smiles. \"The Row speaks well of you. Here -- a "
                      "healing draught at half price. And... the base recipe for "
                      "something stronger. A Memory Potion. Use it wisely.\"",
            "choices": [
                {"label": "Accept the recipe", "icon": "help",
                 "effects": [{"flag": "has_recipe"}, {"flag": "done_sela"},
                             {"note": "You learned the Memory Potion recipe."}],
                 "result": "\"Kindness travels faster than you'd think here.\""},
            ],
        },
        {
            "id": "2A_bad", "act": 2, "max_act": 3, "once": True,
            "gate": [{"trust_lte": ["npc:sela", -0.05]}],
            "prompt": "Sela's eyes narrow. \"I heard what you did. Double price "
                      "for you, and no, you can't have my recipes.\"",
            "choices": [
                {"label": "Pay double, leave", "icon": "coin",
                 "effects": [{"flag": "done_sela"},
                             {"note": "Sela withheld the Memory Potion recipe."}],
                 "result": "\"Word travels. You made your bed.\""},
            ],
        },
        {
            "id": "2A_neutral", "act": 2, "max_act": 3, "once": True,
            "prompt": "Sela studies you. \"I don't know you yet. Prove yourself "
                      "and I might share more than tinctures.\"",
            "choices": [
                {"label": "Offer to help at her clinic", "icon": "help",
                 "effects": [
                     {"remember": {"deed": "helped", "target": "npc:sela",
                                   "summary": "the stranger helped Sela's clinic",
                                   "creates_favor": True}},
                     {"flag": "has_recipe"}, {"flag": "done_sela"},
                     {"improve": "npc:sela"},
                     {"note": "You earned Sela's trust and the recipe."}],
                 "result": "\"...Alright. The Memory Potion recipe is yours.\""},
                {"label": "Just buy a draught", "icon": "coin",
                 "effects": [{"flag": "done_sela"}],
                 "result": "\"Fair enough. Come back if you change your mind.\""},
            ],
        },
        {
            "id": "brew", "act": 4,
            "gate": [{"flag": "has_recipe"}, {"not_flag": "has_potion"}],
            "prompt": "Sela eyes your satchel. \"You have the recipe. If you've a "
                      "binding agent -- forge-salt would do -- I can brew the "
                      "Memory Potion now.\"",
            "choices": [
                {"label": "[If you have forge-salt] Brew the potion", "icon": "help",
                 "gate": [{"item": "item:forge_salt"}],
                 "effects": [{"item_remove": "item:forge_salt"},
                             {"item_add": "item:memory_potion"},
                             {"flag": "has_potion"},
                             {"note": "You brewed the Memory Potion (forget)."}],
                 "result": "The vial glows faintly. \"One grudge, erased clean. "
                           "Choose your target well.\""},
                {"label": "I don't have the ingredient yet", "icon": "ignore",
                 "effects": [],
                 "result": "\"Find some forge-salt. Dorin keeps it by the quench-"
                           "trough.\""},
            ],
        },
    ],

    # ================= CRISPIN (Con Artist) =================
    "npc:crispin": [
        {
            "id": "2C", "act": 2, "max_act": 2, "once": True,
            "prompt": "Crispin sidles up. \"Friend! Small favour: tell Sela you "
                      "were with me last night. Cover a little... misunderstanding "
                      "about her missing coin. There's silver in it.\"",
            "choices": [
                {"label": "Lie for him", "icon": "harm",
                 "effects": [
                     {"remember": {"deed": "harmed", "target": "npc:sela",
                                   "summary": "the stranger lied to cover Crispin's theft"}},
                     {"flag": "lied_for_crispin"}, {"flag": "done_crispin"},
                     {"improve": "npc:sela"},
                     {"note": "Sela may discover the lie."}],
                 "result": "\"Knew you had sense. Sela won't suspect a thing.\""},
                {"label": "Expose him to Sela", "icon": "help",
                 "effects": [
                     {"remember": {"deed": "helped", "target": "npc:sela",
                                   "summary": "the stranger exposed Crispin's theft",
                                   "creates_favor": True}},
                     {"remember": {"deed": "harmed", "target": "npc:crispin",
                                   "summary": "the stranger exposed Crispin"}},
                     {"flag": "exposed_crispin"}, {"flag": "done_crispin"},
                     {"improve": "npc:sela"}, {"improve": "npc:crispin"}],
                 "result": "Sela's face hardens toward Crispin. \"Thank you, "
                           "stranger. I owe you.\" Crispin glares daggers."},
            ],
        },
        {
            "id": "3D", "act": 3, "max_act": 3, "once": True,
            "gate": [{"flag": "exposed_crispin"}],
            "prompt": "Cornered in an alley, Crispin raises his hands. \"You ruined "
                      "me. Go on then -- finish it. Or... don't.\"",
            "choices": [
                {"label": "Spare him", "icon": "help",
                 "effects": [
                     {"remember": {"deed": "helped", "target": "npc:crispin",
                                   "summary": "the stranger spared Crispin",
                                   "creates_favor": True}},
                     {"flag": "spared_crispin"}, {"flag": "done_crispin2"},
                     {"improve": "npc:crispin"},
                     {"note": "Crispin owes you his life."}],
                 "result": "\"...You're not what they say. I won't forget this.\""},
                {"label": "Strike him down", "icon": "harm",
                 "effects": [
                     {"remember": {"deed": "harmed", "target": "npc:crispin",
                                   "summary": "the stranger struck Crispin down"}},
                     {"flag": "struck_crispin"}, {"flag": "done_crispin2"},
                     {"improve": "npc:crispin"}],
                 "result": "He crumples. No ally will come from this quarter."},
            ],
        },
        {
            "id": "3D_skip", "act": 3, "max_act": 3, "once": True,
            "gate": [{"not_flag": "exposed_crispin"}],
            "prompt": "Crispin grins. \"Still friends, eh? Lie low -- the Archon's "
                      "people are asking about you.\"",
            "choices": [
                {"label": "Nod and move on", "icon": "ignore",
                 "effects": [{"flag": "done_crispin2"}],
                 "result": "He melts back into the crowd."},
            ],
        },
    ],

    # ================= RENNA (Old Ally) =================
    "npc:renna": [
        {
            "id": "3C", "act": 3, "max_act": 3, "once": True,
            "prompt": "Renna catches your sleeve. \"You don't remember me. But I "
                      "remember YOU. You were an Archivist -- exiled for REFUSING "
                      "to delete a citizen's memories when the Archon ordered it. "
                      "You were the good one. I still trust you... but I carry a "
                      "secret the Archon would pay for.\"",
            "choices": [
                {"label": "Keep faith with Renna", "icon": "help",
                 "effects": [
                     {"remember": {"deed": "helped", "target": "npc:renna",
                                   "summary": "the stranger kept faith with Renna",
                                   "creates_favor": True}},
                     {"flag": "renna_ally"}, {"flag": "done_renna"},
                     {"improve": "npc:renna"},
                     {"note": "Renna will stand with you at the finale."}],
                 "result": "\"Then we finish this together, like before.\""},
                {"label": "Betray her for the Archon's gold", "icon": "harm",
                 "effects": [
                     {"remember": {"deed": "harmed", "target": "npc:renna",
                                   "summary": "the stranger betrayed Renna to the Archon"}},
                     {"flag": "betrayed_renna"}, {"flag": "done_renna"},
                     {"improve": "npc:renna"},
                     {"note": "Renna is now your enemy."}],
                 "result": "Her face breaks. \"So the Archon was right about who "
                           "you became.\""},
            ],
        },
        {
            "id": "4_blackmail", "act": 4,
            "gate": [{"flag": "renna_ally"}, {"flag": "has_potion"},
                     {"not_flag": "freed_renna"}, {"not_flag": "voss_forgiven"}],
            "prompt": "Renna is trembling. \"The Archon blackmails me with a "
                      "memory of my own -- a shame he holds over me. If you used "
                      "your potion on ME, to erase what he weaponises... I'd be "
                      "free. But you'd spend it, and Voss's grudge would remain.\"",
            "choices": [
                {"label": "Use the potion to free Renna", "icon": "help",
                 "effects": [
                     {"forget": {"target_subject": "npc:renna",
                                 "edges": ["distrusts", "harmed"]}},
                     {"item_remove": "item:memory_potion"},
                     {"flag": "freed_renna"}, {"flag": "used_potion_altruistic"},
                     {"note": "You spent the potion to free Renna, not yourself."}],
                 "result": "The shame lifts from her face. \"I'm... free. "
                           "Whatever happens now, thank you.\""},
                {"label": "Keep the potion for the gate", "icon": "ignore",
                 "effects": [{"flag": "kept_potion_for_self"},
                             {"note": "You kept the potion for your own path."}],
                 "result": "\"I understand. Save yourself first.\""},
            ],
        },
    ],

    # ================= TOWN CRIER (faction fork + act narration) ==========
    "npc:crier": [
        {
            "id": "2B", "act": 2, "max_act": 2, "once": True,
            "prompt": "The Crier unrolls a scroll. \"Two banners court you, "
                      "stranger. The WATCH offers order and the ear of the "
                      "guards. The FREE MARKET offers the loyalty of every "
                      "merchant on the Row. Or you may stand alone. Choose.\"",
            "choices": [
                {"label": "Side with the Watch", "icon": "help",
                 "effects": [{"faction": "faction:watch"},
                             {"flag": "done_faction"},
                             {"note": "You joined the Watch."}],
                 "result": "\"So noted. The guards will hear of it by dusk.\""},
                {"label": "Side with the Free Market", "icon": "help",
                 "effects": [{"faction": "faction:free_market"},
                             {"flag": "done_faction"},
                             {"note": "You joined the Free Market."}],
                 "result": "\"So noted. Every merchant now counts you kin.\""},
                {"label": "Stay independent", "icon": "ignore",
                 "effects": [{"flag": "done_faction"}, {"flag": "independent"},
                             {"note": "You stayed independent -- all paths open."}],
                 "result": "\"A lonelier road. But every door stays open to you.\""},
            ],
        },
    ],

    # ================= THE ARCHON (finale) =================
    "npc:archon": [
        {
            "id": "5_finale", "act": 5, "gate": [{"flag": "passed_gate"}],
            "once": True,
            "prompt": "The Archon spreads his hands over the humming Archive. "
                      "\"You came back. No matter -- I'll simply erase every kind "
                      "thing this town remembers of you. When I'm done, no one "
                      "will lift a finger. FORGET HIM, all of you!\" He begins the "
                      "great erasure. What the town holds now decides everything.",
            "choices": [
                {"label": "Let the town's memory answer", "icon": "help",
                 "effects": [{"ending": "resolve"}],
                 "result": ""},
            ],
        },
    ],
}
