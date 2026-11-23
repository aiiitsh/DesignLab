"""APA sentence templates (Meeting 4 rules). The analysis modules build their paragraphs with the
same formatting helpers; these standalone templates are what the golden-string tests check."""
from __future__ import annotations

from ..common import fmt_df, fmt_num, fmt_p, fmt_unit, p_eq


def strip_md(s: str) -> str:
    return s.replace("*", "")


def t_ind(dv: str, g1: str, g2: str, m1, sd1, m2, sd2, t, df, p, d, digits: int = 1) -> str:
    sig = p < 0.05
    return (f"An independent samples t-test was conducted to compare {dv} in {g1} and {g2} conditions. "
            f"There was {'a' if sig else 'no'} significant difference in the scores for the {g1} group "
            f"(*M* = {fmt_num(m1, digits)}, *SD* = {fmt_num(sd1, digits)}) and the {g2} group "
            f"(*M* = {fmt_num(m2, digits)}, *SD* = {fmt_num(sd2, digits)}); *t*({fmt_df(df)}) = {fmt_num(t)}, "
            f"{p_eq(p)}, *d* = {fmt_num(d)}.")


def rm_gg(chi2, df_chi, p_chi, eps, F, df1, df2, p, eta2, factor: str = "the factor") -> str:
    return (f"Since Mauchly's test indicated that the assumption of sphericity was violated, χ²({df_chi}) = "
            f"{fmt_num(chi2)}, {p_eq(p_chi)}, and the Greenhouse-Geisser ε = {fmt_num(eps)}, Greenhouse-Geisser "
            f"correction was used. The effect of {factor} was {'' if p < .05 else 'not '}significant, "
            f"*F*({fmt_num(df1)}, {fmt_num(df2)}) = {fmt_num(F)}, {p_eq(p)}, η² = {fmt_unit(eta2)}.")


def welch_anova(lev_F, lev_df1, lev_df2, lev_p, F, df1, df2, p, eta2, factor: str = "the factor") -> str:
    return (f"Since Levene's test for equality of variances was significant, *F*({lev_df1}, {lev_df2}) = "
            f"{fmt_num(lev_F)}, {p_eq(lev_p)}, Welch ANOVA test was used. There was {'a' if p < .05 else 'no'} "
            f"significant effect of {factor}, *F*({fmt_df(df1)}, {fmt_df(df2)}) = {fmt_num(F)}, {p_eq(p)}, "
            f"η² = {fmt_unit(eta2)}.")


def regression(F, df1, df2, p, r2, equation: str) -> str:
    return (f"The regression model was {'' if p < .05 else 'not '}significant, *F*({fmt_df(df1)}, {fmt_df(df2)}) = "
            f"{fmt_num(F)}, {p_eq(p)}, *R*² = {fmt_unit(r2)}. {equation}.")


def logistic(pred: str, wald, p_pred, chi2, df_resid, p_model, cs, odds, event_text: str) -> str:
    return (f"In the logistic regression, only the {pred} predictor had a significant effect (*W*(1) = "
            f"{fmt_num(wald)}, {p_eq(p_pred)}). Overall, the regression model was "
            f"{'' if p_model < .05 else 'not '}significant (χ²({df_resid}) = {fmt_num(chi2)}, {p_eq(p_model)}), with "
            f"*R*² = {fmt_unit(cs)} (Cox & Snell). The odds of {event_text} are {odds:.2f} times higher.")


def mann_whitney(dv: str, la: str, mdn_a, lb: str, mdn_b, U, p, r, higher: str | None) -> str:
    def mdn(label, m):
        m = int(m) if float(m).is_integer() else m
        return f"{label[:-1]}; *Mdn* = {m})" if label.endswith(")") else f"{label} (*Mdn* = {m})"
    s = (f"A Mann-Whitney U test was conducted to compare {dv} between the {mdn(la, mdn_a)} and {mdn(lb, mdn_b)} "
         f"groups. ")
    stat = f"*U* = {fmt_num(U, 1)}, {p_eq(p)}, *r* = {fmt_unit(r, 2)}"
    if p < .05 and higher:
        return s + f"{dv[0].upper() + dv[1:]} was significantly higher with {higher}, {stat}."
    return s + f"There was no significant difference between the groups, {stat}."
