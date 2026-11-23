import React, { useState } from "react";
import { useStore } from "../store";

/** Learn mode: what a number is, where it comes from, and which Meeting covers it. */
export const GLOSSARY: Record<string, string> = {
  "t": "t statistic = difference in means / its standard error. df = n₁ + n₂ − 2 (Student) or the Welch–Satterthwaite value (Meeting 4).",
  "df": "Degrees of freedom. Between: k − 1; error: N − k. Decimal df means a correction (Welch, Greenhouse-Geisser, Huynh-Feldt) was applied.",
  "p": "Probability of a result at least this extreme if H₀ were true. p < α → reject H₀ (Type I risk = α). Report exact p to 3 decimals; below .001 write p < .001 (Meeting 4).",
  "F": "F = MS_effect / MS_error. Large F → the effect explains much more variance than chance (Meeting 6).",
  "Sum of Squares": "SS = Σ(squared deviations). SS_total = SS_between + SS_within; η² = SS_between / SS_total (Meeting 6).",
  "Mean Square": "MS = SS / df.",
  "η²": "Eta squared = SS_effect / SS_total; proportion of total variance explained. Bands .01 / .06 / .14 (Meeting 6).",
  "η²p": "Partial eta squared = SS_effect / (SS_effect + SS_error). Used for factorial, RM and mixed designs (Meetings 8–10). G*Power f = √(η²p / (1 − η²p)).",
  "η²G": "Generalized eta squared: comparable across within and between designs.",
  "ω²": "Omega squared: a less biased version of η² (Meeting 6).",
  "Cohen's d": "d = (M₁ − M₂) / pooled SD. .2 small, .5 medium, .8 large (Meeting 4).",
  "Greenhouse-Geisser ε": "Greenhouse-Geisser epsilon; < 0.60 → use GG (Meeting 7); corrected df = (k − 1)·ε.",
  "Huynh-Feldt ε": "Huynh-Feldt epsilon (Lecoutre correction, as JASP). Used when Mauchly p < .05 and GG ε ≥ 0.60 (Meeting 7).",
  "Mauchly's W": "Mauchly's test of sphericity: are the variances of all pairwise differences equal? p > .05 = OK (backwards logic). Needs 3+ levels (Meeting 7).",
  "W": "Shapiro-Wilk W: close to 1 = close to normal. p > .05 = OK (Meeting 4).",
  "SE": "Standard error = SD / √n (Meeting 3).",
  "SD": "Standard deviation (n − 1 in the denominator).",
  "Mean": "Arithmetic mean M.",
  "Median": "Middle value; the line inside a box plot is the median (Meeting 3).",
  "R²": "Proportion of variance in the DV explained by the predictors (Meeting 12). f² = R² / (1 − R²): .02 / .15 / .35.",
  "Adjusted R²": "R² penalized for the number of predictors.",
  "Unstandardized B": "B is in the DV's original units: change in predicted DV per 1-unit increase of the predictor (Meeting 12).",
  "Standardized β": "β compares predictors on a common (SD) scale (Meeting 12).",
  "VIF": "Variance inflation factor; VIF ≥ 10 → multicollinearity. Tolerance = 1/VIF (Meeting 13).",
  "Odds Ratio": "OR = e^b. It multiplies the odds, not the probability: OR = 3 does not mean three times as likely (Meeting 14).",
  "Wald": "Wald = (b / SE)²; like t² for a logistic coefficient, df = 1 (Meeting 14).",
  "Cox & Snell R²": "A pseudo R² for logistic regression (Meeting 14).",
  "Statistic": "The test statistic: t for Student/Welch, U for Mann-Whitney (Meeting 4).",
  "Effect size": "Magnitude of the effect. Significance ≠ magnitude, so always report an effect size (Meeting 3).",
  "Rank-biserial r": "Effect size for Mann-Whitney: r = 2U/(n₁n₂) − 1. Sign follows the A − B direction.",
  "Approx. χ²": "Mauchly's χ² approximation; df = p(p + 1)/2 − 1 with p = k − 1.",
};

export function Learn({ term, children }: { term: string; children?: React.ReactNode }) {
  const { settings } = useStore();
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);
  const text = GLOSSARY[term];
  if (!settings.learn || !text) return <>{children ?? term}</>;
  return (
    <span
      className="learn"
      tabIndex={0}
      onMouseEnter={(e) => setPos({ x: e.clientX, y: e.clientY })}
      onMouseMove={(e) => setPos({ x: e.clientX, y: e.clientY })}
      onMouseLeave={() => setPos(null)}
      onFocus={(e) => { const r = (e.target as HTMLElement).getBoundingClientRect(); setPos({ x: r.left, y: r.bottom }); }}
      onBlur={() => setPos(null)}
    >
      {children ?? term}
      {pos && <span className="tip" style={{ left: Math.min(pos.x + 12, window.innerWidth - 340), top: pos.y + 14 }}>{text}</span>}
    </span>
  );
}
