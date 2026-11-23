# Build decisions and departures from the spec

## Stack
- **Plain CSS tokens instead of Tailwind.** The interface is small, and CSS custom properties give the role colours and dark theme with no build plugin.
- **Custom data grid instead of a grid library.** It handles Excel paste (tab-separated), per-column types, validation and coercion in about 300 lines, with no licence or bundle cost.
- **The built site (`web/dist`) ships with the app** so that running it needs only Python.

## Statistics rules
- **Normality takes precedence over equal variances.** When Shapiro-Wilk fails in any group and Levene also fails, the non-parametric fallback (Mann-Whitney / Kruskal-Wallis) is used, not Welch. The decision log records the Welch result alongside, for example "Welch would be t(15.537) = −3.609, p = .002".
- **Levene is mean-centred**, matching JASP and SPSS rather than scipy's median default.
- **Sphericity:** Mauchly's W uses R's `mauchly.test` second-order correction to the χ² p, which matches JASP. GG is used when ε < .60 and HF otherwise. HF uses the Lecoutre (1991) correction, which JASP and R use, instead of the original Huynh-Feldt formula that can over-correct with mixed designs.
- **Factorial ANOVA uses Type III sums of squares** with sum-to-zero contrasts, which matches JASP/SPSS for unbalanced data.
- **Repeated-measures and mixed ANOVA** compute every stratum from cell totals by inclusion-exclusion. With unequal group sizes across two or more between factors this matches the unweighted-means approach. Results were checked against pingouin.
- **Simple main effects** are run automatically when an interaction is significant, using the full-model error term.
- **Fisher's exact test is offered only for 2×2 tables.** Larger tables report Pearson and the likelihood-ratio χ².
- **Label clean-up:** text levels are trimmed and case variants are merged into the most common spelling, so "yes" and "Yes " count as one level. Values are not title-cased, so "2nd" stays "2nd".

## Power (G*Power parity)
- **One-way ANOVA total N steps in multiples of k** (equal groups), as G*Power does. For f = .25, k = 3 this gives N = 159 (53 per group) rather than 158.
- Two-group t-tests search per-group n, then report the total.
- At very large effects, a power of NaN from the noncentral distribution is clamped to 1.

## Corrections to the spec's expected numbers
- **Case 11 (Album Sales, hierarchical regression):** the spec gives "F change(3,196) ≈ 129.5". Block 2 adds two predictors (airplay, attract), so the correct test is **F change(2, 196) = 96.447**, which matches JASP. The suite tests the corrected value.
- **Montgomery Example 3.1:** the book prints F = 66.80. The exact value is 66.797 and the suite checks that. For Example 6.2 collapsed to three factors, the book prints F = 83.36 / 58.56 / 49.27 from rounded mean squares; the exact values are 83.37 / 58.57 / 49.27, so the tolerance there is 0.02.

## DOE
- Fractional factorial generators follow Montgomery Table XII. Aliases are listed shortest first.
- Orthogonal arrays included are L4, L8, L9, L12, L16 and L27. **L18 is not included** because its mixed 2- and 3-level columns need a separate construction table. Use L9 or L27 for 3-level factors.

## Report
- **One-click PDF needs Playwright** (`pip install playwright` then `python -m playwright install chromium`). Without it the Report page falls back to the browser's Print to PDF, which gives the same layout.
