"use client";

export interface CharacterPresentation {
  character_key: string; version: number; adult: boolean;
  appearance: { portrait_style?: "masculine" | "feminine" | "androgynous"; description: string; skin_tone: string; hair_color: string; eye_color: string; eye_tint: string; hair_style: string; beard: boolean };
  body: { height_cm: number; build: string; outfit_color: string; asset_ref: string };
  voice: { provider: string; language: string; voice_name: string; pitch: number; rate: number; style: string };
}
export default function CharacterAvatar({ presentation, name, compact = false }: { presentation?: CharacterPresentation | null; name: string; compact?: boolean }) {
  if (!presentation) return <span className="office-avatar flex items-center justify-center bg-slate-800 rounded-xl" aria-label={`${name}: appearance unavailable`}>{name.slice(0, 2)}</span>;
  const a = presentation.appearance, b = presentation.body;
  const feminine = a.portrait_style === "feminine";
  const shoulder = b.build === "well_built" ? 65 : b.build === "athletic" ? 56 : b.build === "slender" ? 44 : 50;
  const legs = 90 + (b.height_cm - 140) * .35;
  return <svg className={compact ? "office-avatar" : "w-44 h-64 mx-auto"} viewBox={compact ? "60 0 120 115" : "0 0 240 340"} role="img" aria-label={`${name} character: ${a.description}`}>
    {!compact && <><ellipse cx="120" cy="323" rx="60" ry="9" fill="#0f172a" /><path d={`M92 211L92 ${215 + legs}L113 ${215 + legs}L122 220L133 ${215 + legs}L154 ${215 + legs}L150 211Z`} fill="#182432" /><path d={`M90 ${215 + legs}h25v9H83Z M133 ${215 + legs}h26v9h-26Z`} fill="#090e14" /></>}
    <path d={`M${120 - shoulder} 201Q${120 - shoulder - 12} 139 92 116L148 116Q${120 + shoulder + 12} 139 ${120 + shoulder} 201L154 222H86Z`} fill={b.outfit_color} />
    <path d="M107 107v17l13 22 13-22v-17" fill={a.skin_tone} /><path d="M105 121l15 29 15-29-3 52h-24Z" fill="#e5e7eb" />{!feminine && <path d="M117 142h6l5 46-8 12-8-12Z" fill="#7f1d1d" />}
    {a.hair_style !== "short" && <ellipse cx="120" cy="68" rx="47" ry={a.hair_style === "bob" ? 48 : 57} fill={a.hair_color} />}
    {a.hair_style === "bob" && <path d="M75 44Q66 86 76 117L95 116L91 63H149L145 116L164 117Q174 86 165 44Z" fill={a.hair_color} />}
    {a.hair_style === "long" && <g fill={a.hair_color}><path d="M75 45L72 147L92 136L89 46Z" /><path d="M151 46L148 136L168 147L165 45Z" /></g>}
    {a.hair_style === "bun" && <circle cx="120" cy="15" r="19" fill={a.hair_color} />}
    <ellipse cx="81" cy="69" rx="7" ry="12" fill={a.skin_tone} /><ellipse cx="159" cy="69" rx="7" ry="12" fill={a.skin_tone} />
    <path d={feminine ? "M84 46Q85 18 120 18Q155 18 156 46L151 85Q139 107 120 110Q101 107 89 85Z" : "M82 46Q83 18 120 18Q157 18 158 46L155 85Q143 110 120 113Q97 110 85 85Z"} fill={a.skin_tone} />
    <path d="M83 43Q80 9 120 8Q162 9 158 45L143 33Q109 37 96 29Z" fill={a.hair_color} />
    {a.hair_style === "dreadlocks" && <g fill="none" stroke={a.hair_color} strokeWidth="9" strokeLinecap="round">{[0, 1, 2, 3, 4, 5].map(i => <path key={i} d={`M${87 + i * 13} 25Q${76 + i * 16} 41 ${i < 3 ? 77 - i * 3 : 159 + (i - 3) * 3} ${78 + i * 5}`} />)}</g>}
    {a.hair_style === "curly" && <g fill={a.hair_color}>{[0, 1, 2, 3, 4, 5].map(i => <circle key={i} cx={82 + i * 15} cy={25 + (i % 2) * 7} r="13" />)}</g>}
    <path d="M94 57q11-5 20 0M127 57q10-5 20 0" stroke={a.hair_color} strokeWidth={feminine ? "2" : "3"} fill="none" />
    {[104, 136].map(x => <g key={x}><ellipse cx={x} cy="66" rx="9" ry="5" fill="#e7e5df" /><circle cx={x} cy="66" r="4" fill={a.eye_tint} /><circle cx={x} cy="66" r="2.7" fill={a.eye_color} /><circle cx={x + .8} cy="65" r=".7" fill="#ffffff" /></g>)}
    <path d="M120 68l-4 14h8" stroke="#000000" strokeOpacity=".2" strokeWidth="2" fill="none" />
    {a.beard && <path d="M88 80Q91 105 120 111Q149 105 152 80L139 89L120 98L102 89Z" fill={a.hair_color} fillOpacity=".9" />}
    {feminine && <g fill="none" stroke={b.outfit_color} strokeWidth="2"><circle cx="81" cy="84" r="4" /><circle cx="159" cy="84" r="4" /></g>}
    <path d="M108 94q12 5 24 0" stroke={feminine ? "#9b4c47" : "#2b1613"} strokeWidth={feminine ? "3" : "2"} fill="none" />
  </svg>;
}
