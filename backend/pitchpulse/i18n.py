"""Caption templates per language and voice.

Each template is a list of fragments. A fragment is (conditions, text): it is
included when every condition holds. A condition "x" needs fact x present and
truthy; "!x" needs it absent or falsy. Text is formatted with the fact values,
so template captions can only ever repeat numbers from the fact pack.
"""

LANGS = ("en", "es", "ar")
RTL = {"ar"}

WORDS = {
    "en": {"saved": "saved", "blocked": "blocked", "off_target": "off target", "yellow": "Yellow", "red": "Red"},
    "es": {"saved": "parada del portero", "blocked": "bloqueado", "off_target": "fuera", "yellow": "amarilla", "red": "roja"},
    "ar": {"saved": "تصدى لها الحارس", "blocked": "صُدّت", "off_target": "خارج المرمى", "yellow": "صفراء", "red": "حمراء"},
}

T = {
    "en": {
        "goal": {
            "casual": [((), "GOAL! {scorer} scores for {team}, {score_home}-{score_away}."),
                       (("assister",), " Set up by {assister}."),
                       (("comeback_from",), " {team} have turned {comeback_from} into a lead!"),
                       (("storyline", "!comeback_from"), " The comeback is on."),
                       ((), " Win chance {wp_before}% to {wp_after}%.")],
            "analyst": [((), "Goal {scorer} {minute}' | xG {xg} | shot {shot_speed} km/h."),
                        (("assister",), " Assist {assister}: difficulty {assist_difficulty}/100, {assist_bypassed} opponents bypassed."),
                        (("press_now",), " Opposition press down to {press_now} per 10 passes from a peak of {press_peak}."),
                        ((), " Win probability {wp_before}% to {wp_after}%.")],
        },
        "big_chance": {
            "casual": [((), "So close! Big chance for {player}, {outcome_l}.")],
            "analyst": [((), "Big chance: {player}, xG {xg} from {distance} m, {outcome_l}. Team xG now {team_xg}.")],
        },
        "line_breaker": {
            "casual": [((), "What a pass! {passer} finds {receiver} and cuts out {bypassed} defenders.")],
            "analyst": [((), "Line-breaker: {passer} to {receiver}, {distance} m, difficulty {difficulty}/100, {bypassed} bypassed"),
                        (("pressure",), ", under pressure"),
                        ((), ". Match average difficulty {avg_difficulty}/100.")],
        },
        "sprint": {
            "casual": [((), "{player} hits {speed} km/h!"), (("is_record",), " Fastest run of the match.")],
            "analyst": [((), "Sprint: {player} {speed} km/h over {distance} m, sprint {sprints} today."),
                        (("is_record",), " New match top speed.")],
        },
        "milestone": {
            "casual": [((), "Milestone: {player} reaches {apps} appearances for {club} today.")],
            "analyst": [((), "Milestone: appearance {apps} for {club} for {player}.")],
        },
        "card": {
            "casual": [((), "{card_l} card for {player} after a foul on {fouled}.")],
            "analyst": [((), "{card_l} card: {player} on {fouled}. Tempo before the stoppage {tempo} actions/min.")],
        },
        "press_fade": {
            "casual": [((), "{team}'s press is running out of steam.")],
            "analyst": [((), "{team} pressure index down from {press_then} to {press_now} per 10 opposition passes in 10 min. Opponent completion now {opp_completion}%.")],
        },
        "press_surge": {
            "casual": [((), "{team} are pressing hard now.")],
            "analyst": [((), "{team} pressing surge: {press_then} to {press_now} per 10 opposition passes. Opponent completion {opp_completion}%.")],
        },
        "control_swing": {
            "casual": [((), "{team} are taking control of the game.")],
            "analyst": [((), "Control swing to {team}: control gap {control_then} to {control_now}. Their completion {completion}%, chaos index {chaos}/100.")],
        },
        "rhythm_shift": {
            "casual": [(("up",), "The game has sped up."), (("!up",), "The game has slowed right down.")],
            "analyst": [((), "Tempo {tempo_then} to {tempo_now} actions/min ({change}%), chaos index {chaos}/100.")],
        },
        "player_card": {
            "casual": [((), "{name} so far: {passes_complete} of {passes} passes, {line_breakers} line-breaking passes, top speed {top_speed} km/h.")],
            "analyst": [((), "{name}: {touches} touches, {passes_complete}/{passes} passes, avg difficulty {avg_difficulty}/100, {line_breakers} line-breakers, {interceptions} interceptions, top speed {top_speed} km/h.")],
        },
    },
    "es": {
        "goal": {
            "casual": [((), "¡GOL! {scorer} marca para {team}, {score_home}-{score_away}."),
                       (("assister",), " Asistencia de {assister}."),
                       (("comeback_from",), " ¡{team} remonta un {comeback_from} y se pone por delante!"),
                       (("storyline", "!comeback_from"), " ¡La remontada está en marcha!"),
                       ((), " Probabilidad de victoria: del {wp_before}% al {wp_after}%.")],
            "analyst": [((), "Gol de {scorer} {minute}' | xG {xg} | disparo a {shot_speed} km/h."),
                        (("assister",), " Asistencia de {assister}: dificultad {assist_difficulty}/100, {assist_bypassed} rivales superados."),
                        (("press_now",), " La presión rival cae a {press_now} por cada 10 pases desde un pico de {press_peak}."),
                        ((), " Probabilidad de victoria del {wp_before}% al {wp_after}%.")],
        },
        "big_chance": {
            "casual": [((), "¡Casi! Ocasión clarísima de {player}: {outcome_l}.")],
            "analyst": [((), "Ocasión clara: {player}, xG {xg} desde {distance} m, {outcome_l}. xG del equipo: {team_xg}.")],
        },
        "line_breaker": {
            "casual": [((), "¡Qué pase! {passer} encuentra a {receiver} y deja atrás a {bypassed} rivales.")],
            "analyst": [((), "Pase entre líneas: {passer} a {receiver}, {distance} m, dificultad {difficulty}/100, {bypassed} superados"),
                        (("pressure",), ", bajo presión"),
                        ((), ". Dificultad media del partido {avg_difficulty}/100.")],
        },
        "sprint": {
            "casual": [((), "¡{player} alcanza {speed} km/h!"), (("is_record",), " La carrera más rápida del partido.")],
            "analyst": [((), "Sprint: {player} a {speed} km/h en {distance} m, sprint número {sprints} hoy."),
                        (("is_record",), " Nueva velocidad máxima del partido.")],
        },
        "milestone": {
            "casual": [((), "Hito: {player} llega hoy a {apps} partidos con {club}.")],
            "analyst": [((), "Hito: partido {apps} de {player} con {club}.")],
        },
        "card": {
            "casual": [((), "Tarjeta {card_l} para {player} por una falta sobre {fouled}.")],
            "analyst": [((), "Tarjeta {card_l}: {player} sobre {fouled}. Ritmo antes de la pausa: {tempo} acciones/min.")],
        },
        "press_fade": {
            "casual": [((), "La presión de {team} se está apagando.")],
            "analyst": [((), "Índice de presión de {team}: de {press_then} a {press_now} por cada 10 pases rivales en 10 min. El rival ya completa el {opp_completion}% de sus pases.")],
        },
        "press_surge": {
            "casual": [((), "{team} aprieta arriba con fuerza.")],
            "analyst": [((), "Subida de presión de {team}: de {press_then} a {press_now} por cada 10 pases rivales. Acierto rival {opp_completion}%.")],
        },
        "control_swing": {
            "casual": [((), "{team} toma el control del partido.")],
            "analyst": [((), "Cambio de control hacia {team}: diferencia de control de {control_then} a {control_now}. Acierto en el pase {completion}%, índice de caos {chaos}/100.")],
        },
        "rhythm_shift": {
            "casual": [(("up",), "El partido se ha acelerado."), (("!up",), "El partido se ha frenado por completo.")],
            "analyst": [((), "Ritmo de {tempo_then} a {tempo_now} acciones/min ({change}%), índice de caos {chaos}/100.")],
        },
        "player_card": {
            "casual": [((), "{name} hasta ahora: {passes_complete} de {passes} pases, {line_breakers} pases entre líneas, velocidad máxima {top_speed} km/h.")],
            "analyst": [((), "{name}: {touches} toques, {passes_complete}/{passes} pases, dificultad media {avg_difficulty}/100, {line_breakers} pases entre líneas, {interceptions} intercepciones, velocidad máxima {top_speed} km/h.")],
        },
    },
    "ar": {
        "goal": {
            "casual": [((), "هدف! {scorer} يسجل لـ{team}، النتيجة {score_home}-{score_away}."),
                       (("assister",), " بتمريرة من {assister}."),
                       (("comeback_from",), " {team} يقلب تأخره {comeback_from} إلى تقدم!"),
                       (("storyline", "!comeback_from"), " العودة بدأت!"),
                       ((), " فرصة الفوز من {wp_before}% إلى {wp_after}%.")],
            "analyst": [((), "هدف {scorer} في الدقيقة {minute} | xG {xg} | سرعة التسديدة {shot_speed} كم/س."),
                        (("assister",), " صناعة {assister}: صعوبة التمريرة {assist_difficulty}/100، تجاوزت {assist_bypassed} لاعبين."),
                        (("press_now",), " ضغط المنافس تراجع إلى {press_now} لكل 10 تمريرات بعد ذروة {press_peak}."),
                        ((), " احتمال الفوز من {wp_before}% إلى {wp_after}%.")],
        },
        "big_chance": {
            "casual": [((), "يا لها من فرصة! فرصة كبيرة لـ{player}، {outcome_l}.")],
            "analyst": [((), "فرصة كبيرة: {player}، xG {xg} من {distance} م، {outcome_l}. مجموع xG للفريق {team_xg}.")],
        },
        "line_breaker": {
            "casual": [((), "تمريرة رائعة! {passer} يجد {receiver} ويتجاوز {bypassed} مدافعين.")],
            "analyst": [((), "تمريرة تكسر الخطوط: {passer} إلى {receiver}، {distance} م، الصعوبة {difficulty}/100، تجاوزت {bypassed}"),
                        (("pressure",), "، تحت الضغط"),
                        ((), ". متوسط صعوبة التمرير في المباراة {avg_difficulty}/100.")],
        },
        "sprint": {
            "casual": [((), "{player} يصل إلى {speed} كم/س!"), (("is_record",), " أسرع انطلاقة في المباراة.")],
            "analyst": [((), "انطلاقة: {player} بسرعة {speed} كم/س لمسافة {distance} م، الانطلاقة رقم {sprints} اليوم."),
                        (("is_record",), " أعلى سرعة في المباراة حتى الآن.")],
        },
        "milestone": {
            "casual": [((), "إنجاز: {player} يخوض مباراته رقم {apps} مع {club} اليوم.")],
            "analyst": [((), "إنجاز: المباراة رقم {apps} لـ{player} مع {club}.")],
        },
        "card": {
            "casual": [((), "بطاقة {card_l} لـ{player} بعد خطأ على {fouled}.")],
            "analyst": [((), "بطاقة {card_l}: {player} على {fouled}. الإيقاع قبل التوقف {tempo} إجراء/دقيقة.")],
        },
        "press_fade": {
            "casual": [((), "ضغط {team} بدأ يفقد قوته.")],
            "analyst": [((), "مؤشر ضغط {team} انخفض من {press_then} إلى {press_now} لكل 10 تمريرات للمنافس خلال 10 دقائق. دقة تمرير المنافس الآن {opp_completion}%.")],
        },
        "press_surge": {
            "casual": [((), "{team} يضغط بقوة الآن.")],
            "analyst": [((), "ارتفاع ضغط {team}: من {press_then} إلى {press_now} لكل 10 تمريرات للمنافس. دقة المنافس {opp_completion}%.")],
        },
        "control_swing": {
            "casual": [((), "{team} يفرض سيطرته على المباراة.")],
            "analyst": [((), "تحول السيطرة إلى {team}: فارق السيطرة من {control_then} إلى {control_now}. دقة التمرير {completion}%، مؤشر الفوضى {chaos}/100.")],
        },
        "rhythm_shift": {
            "casual": [(("up",), "إيقاع المباراة تسارع."), (("!up",), "إيقاع المباراة تباطأ كثيرًا.")],
            "analyst": [((), "الإيقاع من {tempo_then} إلى {tempo_now} إجراء/دقيقة ({change}%)، مؤشر الفوضى {chaos}/100.")],
        },
        "player_card": {
            "casual": [((), "{name} حتى الآن: {passes_complete} من {passes} تمريرة، {line_breakers} تمريرات تكسر الخطوط، أعلى سرعة {top_speed} كم/س.")],
            "analyst": [((), "{name}: {touches} لمسة، {passes_complete}/{passes} تمريرة، متوسط الصعوبة {avg_difficulty}/100، {line_breakers} تمريرات تكسر الخطوط، {interceptions} اعتراضات، أعلى سرعة {top_speed} كم/س.")],
        },
    },
}

RECAP = {
    "en": {
        "title_ft": "Full-time recap", "title_ht": "Half-time recap",
        "score": "{home} {hg}-{ag} {away}.",
        "comeback": "{team} came back from {from_score} down with {n} goals after minute {after}.",
        "press": "The story turned on {team}'s press: it peaked at {peak} per 10 opposition passes, then faded to {now} by minute {faded_at}.",
        "wp": "At its lowest, {team}'s win probability was {low}% in minute {low_min}.",
        "xg": "Expected goals: {home} {hxg}, {away} {axg}.",
        "pom": "Player of the match: {name} ({team}), {assists} assists, {line_breakers} line-breaking passes and {passes_complete} completed passes.",
        "fastest": "Fastest run: {sprint_name} at {sprint_speed} km/h. Hardest shot: {shot_name} at {shot_speed} km/h.",
        "lead": "{team} lead at the break with goals from {scorers}.",
        "level": "All square at the break.",
    },
    "es": {
        "title_ft": "Resumen final", "title_ht": "Resumen del descanso",
        "score": "{home} {hg}-{ag} {away}.",
        "comeback": "{team} remontó un {from_score} con {n} goles después del minuto {after}.",
        "press": "La clave fue la presión de {team}: llegó a {peak} por cada 10 pases rivales y cayó a {now} hacia el minuto {faded_at}.",
        "wp": "En su peor momento, la probabilidad de victoria de {team} fue del {low}% en el minuto {low_min}.",
        "xg": "Goles esperados: {home} {hxg}, {away} {axg}.",
        "pom": "Jugador del partido: {name} ({team}), {assists} asistencias, {line_breakers} pases entre líneas y {passes_complete} pases completados.",
        "fastest": "Carrera más rápida: {sprint_name} a {sprint_speed} km/h. Disparo más potente: {shot_name} a {shot_speed} km/h.",
        "lead": "{team} gana al descanso con goles de {scorers}.",
        "level": "Empate al descanso.",
    },
    "ar": {
        "title_ft": "ملخص نهاية المباراة", "title_ht": "ملخص الشوط الأول",
        "score": "{home} {hg}-{ag} {away}.",
        "comeback": "{team} عاد من تأخر {from_score} وسجل {n} أهداف بعد الدقيقة {after}.",
        "press": "تحولت المباراة مع ضغط {team}: بلغ ذروته عند {peak} لكل 10 تمريرات للمنافس ثم تراجع إلى {now} بحلول الدقيقة {faded_at}.",
        "wp": "في أسوأ لحظاته، كانت فرصة فوز {team} {low}% في الدقيقة {low_min}.",
        "xg": "الأهداف المتوقعة: {home} {hxg}، {away} {axg}.",
        "pom": "أفضل لاعب: {name} ({team})، {assists} تمريرات حاسمة، {line_breakers} تمريرات تكسر الخطوط و{passes_complete} تمريرة صحيحة.",
        "fastest": "أسرع انطلاقة: {sprint_name} بسرعة {sprint_speed} كم/س. أقوى تسديدة: {shot_name} بسرعة {shot_speed} كم/س.",
        "lead": "{team} يتقدم بين الشوطين بأهداف {scorers}.",
        "level": "التعادل بين الشوطين.",
    },
}

UI_MODES = ("casual", "analyst", "player")


def voice(mode: str) -> str:
    """Player focus reads in the casual voice; its extra content is the player cards."""
    return "analyst" if mode == "analyst" else "casual"
