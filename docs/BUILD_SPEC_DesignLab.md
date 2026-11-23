# DesignLab: build specification for a local experiment-design and analysis tool

> **For Claude Code.** This file is the full brief. Read all of it before writing code, then build in the phase order in §13. After each phase, run the validation suite in §12. Do not move on while a case is failing. When the spec doesn't decide something, pick the simplest option that keeps every result the same as JASP and G*Power, and write the choice down in `docs/DECISIONS.md`.

Owner: Ahmed Hesham Desoky (21280040), SYDE 640 Experimental Design, University of Waterloo (Prof. Shi Cao).

---

## 1. What we are building

**DesignLab** is a website that runs locally on the student's laptop. It covers SYDE 640 from start to finish and replaces JASP and G*Power for everything taught in the course. A **guided wizard** walks the user through the course's decision flow chart one question at a time. The answers lead to:

1. **The right design.** For example: within, between or mixed; t-test, ANOVA, regression, logistic or χ²; a 2ᵏ, fractional factorial, response surface or robust design.
2. **A sample-size plan**, from a built-in power calculator that gives the same numbers as G*Power.
3. **A data sheet with the correct shape** (wide for within factors, long for between factors). The user can type data in, paste it from Excel, or import a CSV or XLSX file.
4. **The full analysis**:
   - descriptives and plots;
   - assumption checks, with the course's fallback rules applied automatically;
   - the main test, post hoc tests or simple main effects, and effect sizes.
5. **A finished report.** It includes an APA-style results paragraph, all tables and figures, a plain-English interpretation, and the equivalent Python code. It can be exported to PDF and HTML.

The user can also skip the wizard and open any analysis directly ("expert mode"), as in JASP's menus.

### Non-goals
- No cloud, no accounts, no telemetry. Everything runs offline once the dependencies are installed.
- No multinomial or ordinal regression, no MANOVA, and no mixed-effects or multilevel models. The course doesn't teach them. Show a short "not covered in SYDE 640" note when the wizard reaches these cases.

---

## 2. Tech stack (fixed)

| Layer | Choice | Why |
|---|---|---|
| Stats engine | **Python 3.11+**, `numpy`, `pandas`, `scipy`, `statsmodels`, `pingouin`, `scikit-posthocs`, `pyDOE3` | Gives the same numbers as JASP; the user already works in Python |
| API | **FastAPI** + `uvicorn`, `pydantic` v2 models | Typed request and response models, auto-generated OpenAPI docs |
| Frontend | **React 18 + TypeScript + Vite**, Tailwind CSS, `@tanstack/react-table`, **Plotly.js** (`react-plotly.js`) | Spreadsheet-style data grid, interactive plots |
| Grid editing | `react-data-grid` (or a small custom grid built on TanStack) | Pasting from Excel needs to work |
| Reports | HTML templates (Jinja2) → PDF through Playwright/Chromium | Same pipeline as the course notes |
| Storage | One `.dlab` project file (a zip holding `project.json`, `data/*.csv` and `report/`) | Portable and easy to inspect |
| Tests | `pytest` (engine), `vitest` + Playwright (UI) | — |

**Launch:** one command, `python run.py`. It installs nothing. It starts the API on `127.0.0.1:8640`, serves the built frontend from the same port, and opens the browser. Also provide `make dev` for hot reload (Vite on 5173, with a proxy to the API).

### Repository layout
```
designlab/
  run.py                     # starts API + static frontend, opens browser
  engine/                    # pure-Python stats, no web code (importable, unit-tested)
    descriptives.py
    assumptions.py           # shapiro, levene, mauchly (+GG/HF eps), qq data
    ttests.py  anova.py  rm_anova.py  mixed_anova.py  factorial.py
    nonparametric.py         # mann-whitney, wilcoxon, kruskal(+dunn), friedman(+conover)
    posthoc.py  contrasts.py  effect_sizes.py
    regression.py  logistic.py  chisquare.py
    power/                   # G*Power-equivalent calculators
    doe/                     # two_level.py fractional.py rsm.py robust.py
    report/                  # apa.py (sentences), templates/, codegen.py (python export)
    decision_tree.py         # loads flowchart.json, evaluates answers -> recommendation
  api/                       # FastAPI routers, pydantic schemas
  web/                       # React app
  data/flowchart.json        # the decision tree (see §4) – single source of truth
  tests/fixtures/            # course datasets (see §12)
  docs/DECISIONS.md
```

---

## 3. Screens and UX

Design language: the HW3 flow chart, which is in the project folder at `hw3/HW3_Flow_Chart_Ahmed_Desoky_21280040.pdf`. Copy it into `docs/` and use it as the visual reference. Every screen uses the chart's colors for the same roles:

| Role | Color | Use |
|---|---|---|
| Decision / question | amber `#e9a400` on `#fff4d4`, hexagon badge | Wizard questions |
| Design step | indigo `#4f55c9` | Planning steps |
| Recommended test | teal `#0d8a87` | Result headers |
| Assumption check | violet `#7a4ed6` | Assumption panel |
| Violated → alternative | coral `#e0532c` | Fallback notices |
| Follow-up / effect size | sky `#2483cc` | Post hoc, effect-size cards |
| Lanes | A teal · B blue `#2f6fd0` · C violet `#8a4fc9` · D orange `#e07a1f` | Breadcrumb color |

Font: Inter, with JetBrains Mono for code. Support light and dark themes.

### 3.1 Home
Three large cards: **Start a new experiment (guided)**, **Open project**, **Quick analysis (expert mode)**. Below them, a list of recent projects and a "Course examples" gallery that opens each fixture from §12 as a ready-made project.

### 3.2 Wizard (the heart of the app)
- A left rail shows the path so far as a mini flow chart. Each answered node is a chip, and clicking any chip goes back to that question.
- The center shows **one question at a time**, with large option cards. Each card has a one-line consequence ("Choose this if…") and a "Why does this matter?" expander. The expander's text comes from the course: carryover, individual differences, and so on.
- The right panel shows the **live recommendation**. As answers come in, the candidate tests narrow down. It also shows which lecture covers the current question (e.g. "Meeting 7").
- Numeric questions (number of levels, number of factors) use steppers.
- A **"Not sure?" helper** sits on the hard questions. Example: for "within or between?", it asks about learning effects, session length, how many participants are available, and whether the IV is a person attribute (gender, age), then suggests an answer.
- At the end, the **Design summary** shows:
  - the design name (e.g. "2 × 3 mixed design: gender between, display within");
  - the IV, DV and control variables, with data types;
  - the counterbalancing plan, with a generated Latin square or full permutation order table that can be downloaded as CSV;
  - a randomization schedule (participant → condition or order), with a seed;
  - the sample-size result from §6;
  - the **data template**: an empty sheet with the correct columns, which feeds straight into §3.3.

### 3.3 Data
- A spreadsheet grid. Column types are Numeric, Nominal or Ordinal, as in JASP; show a type icon in each header and allow labels for factor levels.
- Import CSV, XLSX or JASP-exported CSV, or paste from Excel. Export CSV.
- A **Reshape** button converts between wide and long format. Within factors must be wide, as in JASP (one column per condition); the engine converts internally.
- Validation: show missing values, cells that aren't numeric, groups with fewer than 2 values, and unbalanced cells, with a warning but no block.

### 3.4 Analysis results (one page per analysis)
Cards appear in this order. It matches the report order the course teaches.
1. **Descriptives**: N, M, SD, SE, Mdn, min, max and 95% CI per cell, plus a box plot or raincloud plot. Box plots draw the median line, whiskers at 1.5 × IQR, and outliers as dots.
2. **Assumption checks** (violet): each check shows the test, its statistic, p and a verdict chip. Remember the "backwards" logic: p > .05 means OK. Include Q-Q plots.
3. **Decision log** (coral when something switched). Example: "Levene p = .039 < .05 → switched to Welch ANOVA (course rule, Meeting 6)." The user can override the switch with a toggle; the override is recorded in the report.
4. **Main result**: a table laid out like JASP's, with all the columns JASP shows.
5. **Follow-ups** (sky): post hoc tests, contrasts, simple main effects, interaction plot.
6. **Effect sizes**, each with its interpretation band.
7. **APA paragraph** (§9), with a copy button.
8. **Python code** that reproduces the analysis (§9.3), with a copy button.

### 3.5 Power (built-in G*Power)
A separate page, also embedded in the wizard. See §6.

### 3.6 DOE workspace
Lane D: design generator → run sheet → enter responses → effects → model → optimize → robust. See §8.

### 3.7 Learn mode (toggle)
When on, every number in the output has a hover card. It explains what the number is, where it comes from (formula), and which Meeting covers it. Example: hovering "ε = 0.533" reads "Greenhouse-Geisser epsilon; < 0.60 → use GG (Meeting 7); df = (k−1)·ε". This makes the app a study tool for the course too.

---

## 4. The decision tree (`data/flowchart.json`)

All wizard logic is **data**, not code. Each node has: `id`, `type` (`question` | `numeric` | `outcome`), `lane`, `text`, `help`, `lecture`, `options[{label, consequence, next | outcome}]`. Outcomes point to analysis ids from §5. Build the tree to match the HW3 chart exactly:

**Stage 1: Plan.** These answers are stored in the design summary:
1. Research question (free text) and hypotheses: H₀/H₁, with a choice of two-sided, or one-sided with a direction (fixed before the data are seen).
2. Variables: list the IVs (name, levels, data type) and DVs (name, data type, unit), plus control variables. Use NOIR data types.
3. "Can you manipulate the IV and randomly assign?" → true experiment, or quasi-experiment (flag "weaker causal claim").
4. For each IV: "Does every participant do every level?" → within, between, or (when there are several IVs) mixed. Include the "Not sure?" helper.
5. Controls checklist: randomization; counterbalancing (full or Latin square; generate it); blocking; practice trials; placebo or double-blind.
6. → sample size (§6) → ethics reminder → data template.

**Stage 2: Choose the lane.** "What is the goal and what type are the DV and IV(s)?"
- **A. Compare conditions** (numeric DV, categorical IVs):
  - 1 IV, 2 levels, between → independent t-test.
  - 1 IV, 2 levels, within → paired t-test.
  - 1 IV, 3+ levels, between → one-way ANOVA.
  - 1 IV, 3+ levels, within → one-way RM ANOVA.
  - 2+ IVs, all between → factorial ANOVA.
  - 2+ IVs, all within → two-way (n-way) RM ANOVA.
  - 2+ IVs, some of each → mixed ANOVA.
  - Then: "Is the interaction significant?" → simple main effects, or main effects plus post hoc tests. This step is automatic, driven by the result.
- **B. Relationship** (numeric DV, continuous IVs):
  - 1 predictor → simple linear regression.
  - 2+ predictors → "theory- or data-driven?" → hierarchical (blocks), or forward, backward or stepwise → multiple linear regression.
- **C. Categorical outcome:**
  - binary DV → binary logistic regression;
  - categorical IV × categorical DV counts → χ² test of independence (Fisher's exact test when expected counts are < 5);
  - 3+ categories → "not covered" note.
- **D. Engineering DOE:**
  - "Many candidate factors?" → 2ᵏ.
  - "Budget for all runs?" → replicated full factorial; single replicate (effects, normal plot, then a reduced model); or fractional 2ᵏ⁻ᵖ.
  - "Need the optimum / is there curvature?" → RSM.
  - "Noise factors present?" → robust parameter design.

Write `engine/decision_tree.py` with `next_node(answers)` and `recommend(answers) -> {analysis_id, design_name, data_shape, power_family}`, and unit-test every path.

---

## 5. Analyses: exact behaviour

General rules for **every** test:
- α defaults to .05 and can be changed. Tails can be two-sided or one-sided; for a one-sided test, check the direction and halve p only when the data go the predicted way.
- **Course fallback rules apply automatically.** Each switch is logged in the Decision log, and the user can override it.
- p-values display with 3 decimals, and as "< .001" below that, never ".000".
- Every number appears in the UI exactly as in the report.

### 5.1 Assumption checks (`assumptions.py`)
| Check | Method | Rule |
|---|---|---|
| Normality | Shapiro-Wilk per group (t-test, ANOVA), on paired differences (paired t), on residuals (factorial, regression); Q-Q plot data | p < .05 → non-normal |
| Equal variances | **Levene, centered on the mean**, matching JASP's default (`scipy.stats.levene(center='mean')`) | p < .05 → unequal |
| Sphericity | Mauchly's W, χ², df, p; Greenhouse-Geisser ε and Huynh-Feldt ε (use the Huynh-Feldt formula with the Lecoutre correction to match JASP); only when there are ≥ 3 levels | p < .05 → **ε < 0.60 → GG, else HF** (course rule, Meetings 7/9, after Blanca et al. 2023) |
| Regression | Residual normality (Shapiro + Q-Q), residuals vs fitted (homoscedasticity), VIF/tolerance, condition index, standardized residuals beyond ±2 (expect about 5%), Cook's D > 1 | — |
| χ² | Expected counts per cell | any < 5 → Fisher's exact (2×2), or a warning (larger tables) |

### 5.2 Lane A tests
| id | Test | Implementation | Fallbacks (auto) | Effect sizes | Follow-ups |
|---|---|---|---|---|---|
| `ttest_ind` | Student t | `scipy.stats.ttest_ind(equal_var=True)` | Levene p<.05 → **Welch** (`equal_var=False`); non-normal → **Mann-Whitney U** (report U, p, rank-biserial r) | Cohen's d (pooled SD) + 95% CI; Welch → d with average SD; Hedges g optional | — |
| `ttest_paired` | Paired t | `ttest_rel` | non-normal differences → **Wilcoxon signed-rank** (W, p, matched rank-biserial) | Cohen's d_z = mean diff / SD diff (JASP default) | — |
| `anova_oneway` | One-way ANOVA | `statsmodels` OLS + `anova_lm(typ=2)` | unequal variances → **Welch ANOVA** (`pingouin.welch_anova`), offer Brown-Forsythe; non-normal → **Kruskal-Wallis** + **Dunn** (Bonferroni/Holm) | η², ω² | Post hoc: Tukey (default), Bonferroni, Holm, Šidák, Scheffé, LSD (uncorrected, labelled); Welch → **Games-Howell**. Contrasts: polynomial (linear/quadratic/cubic, equal spacing or user values), treatment, deviation, custom weights |
| `anova_rm1` | One-way RM ANOVA | `pingouin.rm_anova(correction=True, detailed=True)` | sphericity rule above; non-normal → **Friedman** + **Conover** post hoc (`scikit_posthocs.posthoc_conover_friedman`) | η², partial η², generalized η² | Pairwise paired t with Bonferroni/Holm |
| `anova_factorial` | n-way between ANOVA | OLS `y ~ C(A)*C(B)*…`, **Type III SS with sum-to-zero contrasts** (JASP default) | no nonparametric option: offer (a) log/sqrt transform, (b) split into one-ways + Bonferroni, (c) proceed with a caveat sentence | partial η², η², ω² | Interaction significant → **simple main effects** (effect of A at each level of B and vice versa; a + b of them), interaction plot with SE/CI bars; otherwise main-effect post hoc tests for factors with ≥ 3 levels |
| `anova_rm` | n-way RM ANOVA | `pingouin.rm_anova(within=[A,B])` for 2 factors; for 3+ use `statsmodels.AnovaRM` plus own GG/HF per effect | GG/HF per effect; Friedman one factor at a time | partial η² | Simple main effects as above |
| `anova_mixed` | Mixed ANOVA | `pingouin.mixed_anova` (1 within + 1 between); general case: build the error strata yourself (split-plot SS) | within → GG/HF; between → Levene p<.05 → transform / split / caveat (no Welch) | partial η² | Simple main effects; post hoc |

Interaction plots for 3-way designs are split into panels by the third factor (as in the Meeting 10 speed-dating example). The wizard warns at 4+ factors: "four-way and higher interactions are very hard to explain".

### 5.3 Lane B regression (`regression.py`)
- OLS with any mix of continuous predictors and dummy-coded factors (k − 1 dummies; choose the reference level).
- **Entry methods**:
  - Enter;
  - Hierarchical blocks: report each model's R², adjusted R², ΔR², F change, df1, df2 and p change;
  - Forward: enter by highest |r|, then by largest semi-partial; p-to-enter .05;
  - Backward: p-to-remove .10;
  - Stepwise: forward with a removal test after each step.
  - Match JASP's criteria (p-based).
- **Output tables, as in JASP**:
  - Model Summary (R, R², adj R², RMSE, plus R² change);
  - ANOVA (model F);
  - Coefficients: B, SE, β (standardized), t, p, 95% CI, tolerance, VIF;
  - Collinearity diagnostics: eigenvalue, condition index, variance proportions;
  - Casewise diagnostics: |standardized residual| > 2, Cook's D.
- Effect size f² = R²/(1−R²), with small / medium / large bands at .02 / .15 / .35.
- Plots: scatter with fitted line and CI band; residuals vs fitted; Q-Q of residuals; partial plots.
- Fallback suggestions (no automatic switch): transform the DV, add polynomial terms, a GLM, or drop or combine collinear predictors.
- Equation string, e.g. `BMI = 29.578 − 0.655 × PA`.

### 5.4 Lane C (`logistic.py`, `chisquare.py`)
- **Binary logistic** (`statsmodels.Logit`), with covariates (numeric) and factors (dummies). Methods: Enter and stepwise.
- Output in JASP's form:
  - model summary: deviance, AIC, BIC, df, Δχ², p, McFadden / Nagelkerke / Tjur / Cox & Snell R²;
  - coefficients: estimate, SE, **odds ratio = e^b** with 95% CI, z, Wald, df, p;
  - confusion matrix at a 0.5 cutoff;
  - predicted-probability curve.
- Teach the odds-vs-probability trap in Learn mode.
- **χ² test of independence**: observed and expected tables, Pearson χ², df, p, likelihood-ratio χ², **Fisher's exact** (2×2), Cramér's V, odds ratio (2×2), standardized residuals with a heat-map table.

### 5.5 Descriptives and helpers
- Mean, SD (n−1), SE = SD/√n, median, quartiles, IQR, 95% CI (t-based).
- A **confidence-interval calculator** and a "how many t-tests → familywise α" demo (Meeting 6: 10 tests ≈ 40% chance of a false alarm).

---

## 6. Power analysis: built-in G*Power

Implement the calculations from noncentral distributions in `scipy.stats` (`nct`, `ncf`, `ncx2`). **Don't** rely only on `statsmodels.stats.power`, because G*Power's RM-ANOVA parameterisation differs from it.

Each calculator supports these modes:
- **A priori**: solve for N;
- **Post hoc**: power from N;
- **Sensitivity**: minimal effect from N;
- **Criterion**: α from the other values.

Each calculator also has:
- an **effect-size helper**: compute d from two means and SDs, f from group means and SD, f² from R², w from a proportion table, partial η² ↔ f;
- a **power curve** plot (power vs N);
- a "**how to report**" sentence.

| Family | G*Power name to mirror | Inputs | Noncentrality |
|---|---|---|---|
| t | Means: difference between two independent means | d, α, power, tails, allocation ratio N2/N1 | δ = d·√(n1·n2/(n1+n2)), df = N−2 |
| t | Means: difference between two dependent means (matched pairs) | d_z, α, power, tails | δ = d_z·√n, df = n−1 |
| F | ANOVA: fixed effects, omnibus, one-way | f, α, power, k groups | λ = f²·N, df1 = k−1, df2 = N−k |
| F | ANOVA: fixed effects, special, main effects and interactions | f, α, power, numerator df, number of groups (cells) | λ = f²·N, df2 = N − cells |
| F | ANOVA: repeated measures, within factors | f, α, power, groups, measurements m, corr ρ among measures, nonsphericity ε | λ = f²·N·m·ε/(1−ρ); df1 = (m−1)ε; df2 = (N−groups)(m−1)ε |
| F | ANOVA: repeated measures, between factors | f, α, power, groups, m, ρ | λ = f²·N·m/(1+(m−1)ρ); df1 = groups−1; df2 = N−groups |
| F | ANOVA: repeated measures, within-between interaction | f, α, power, groups, m, ρ, ε | λ = f²·N·m·ε/(1−ρ); df1 = (groups−1)(m−1)ε; df2 = (N−groups)(m−1)ε |
| F | Linear multiple regression: fixed model, R² deviation from zero | f², α, power, number of predictors p | λ = f²·N, df1 = p, df2 = N−p−1 |
| F | Linear multiple regression: R² increase | f², α, power, tested predictors q, total predictors p | λ = f²·N, df1 = q, df2 = N−p−1 |
| χ² | Goodness-of-fit / contingency | w, α, power, df | λ = w²·N |
| z | Logistic regression (optional, mark "approximate") | odds ratio, Pr(Y=1 \| X=1)H0, X distribution | Hsieh et al. (1998) |

The wizard explains the G*Power inputs that confuse people:
- **number of groups** = combinations of the between factors;
- **number of measurements** = combinations of the within factors (3 × 3 → 9);
- for a factorial ANOVA, **number of groups** = cells and **numerator df** = the effect's df.

Defaults: α = .05, power = .80, medium effect (d = .5, f = .25, f² = .15, w = .3), ρ = .5, ε = 1.

---

## 7. Design utilities (Stage 1)
- **Counterbalancing generator.** Full permutations (n!) or a **balanced Latin square**: Williams design for an even n; for an odd n, two squares. Output an order × participant table and assign participants in a cycle. Include a check that each condition appears once per row and column.
- **Randomizer.** Random assignment to groups (with optional blocking or stratification) and random run order, both seeded, exported to CSV.
- **Data-type quiz** (NOIR) and a **"which variables?"** builder that turns the RQ into IV, DV and control variables, with operational-definition prompts.

---

## 8. Lane D: DOE workspace (`engine/doe/`)

### 8.1 Two-level factorial 2ᵏ (Meeting 10)
- Enter the factor names, low/high levels in real units, the number of replicates and the number of center points. Generate the run sheet in **standard order**, with run labels `(1), a, b, ab, …`, and a randomized run order (seeded).
- After the responses are entered:
  - the **sign table** for all 2ᵏ−1 effects (an interaction sign is the product of its factors' signs);
  - **effect estimates** (ȳ₊ − ȳ₋);
  - SS = N·effect²/4;
  - **% contribution**;
  - a **normal probability plot** and a **half-normal plot** of the effects, with Lenth's PSE margin lines for unreplicated designs;
  - a Pareto chart.
- With replicates: a full ANOVA. With one replicate: the user (or "auto: drop effects inside Lenth's margin") chooses which terms to keep → a **reduced model**. Dropping a factor collapses the design into a 2ᵏ⁻¹ with replicates (as in the filtration example) → ANOVA.
- Main-effect and interaction plots, a cube plot for 3 factors, and a regression equation in coded and real units.
- A sensitivity tips panel: more replicates, levels farther apart, avoid ceiling and floor effects.

### 8.2 Fractional factorial 2ᵏ⁻ᵖ (Meeting 11)
- The user picks k and p. Offer standard minimum-aberration generators (Montgomery Appendix Table XII) for k ≤ 11, or custom generators (e.g. `D = ABC`, or `E = −ABCD`).
- Show:
  - the **defining relation** (all words);
  - the **resolution** (III, IV, V…);
  - the **complete alias structure** up to 3-factor interactions, with signs.
- Run sheet → effect estimates labelled with their alias chains, e.g. `[A] → A + BCD`.
- A **fold-over / other-half** generator (I = −ABCD). Combining the two halves gives back the full factorial and de-aliases the effects.
- Calculator widgets that copy the midterm question types:
  - number of runs;
  - "alias of X under I = …";
  - "missing level in a run given the defining relation".

### 8.3 Response surface methodology (Montgomery Ch. 11)
- **Curvature test** from center points: SS_curvature = n_F·n_C(ȳ_F − ȳ_C)²/(n_F + n_C).
- **Steepest ascent/descent**: from a first-order model, compute the path in coded and real units with a chosen step. The user records the path responses and sees where the response peaks.
- **Second-order designs**:
  - CCD: face-centered, rotatable α = (2ᵏ)^¼ or (2ᵏ⁻ᵖ)^¼, or orthogonal α;
  - Box-Behnken;
  - choose the number of center points.
- Fit a full quadratic model. Show the ANOVA (linear, quadratic, interaction, lack-of-fit, pure error), the **stationary point** (x_s = −½B⁻¹b) and the **canonical analysis** (eigenvalues → maximum, minimum or saddle).
- 2-D contour and 3-D surface plots (Plotly) for any pair of factors, with the others held at a chosen value.
- **Multiple responses**: overlay contour plot and Derringer-Suich **desirability**, with target, minimize or maximize for each response.

### 8.4 Robust parameter design (Taguchi; Montgomery Ch. 12)
- Tag each factor as **control (x)** or **noise (z)**.
- **Crossed-array mode**:
  - inner array (orthogonal arrays L4, L8, L9, L12, L16, L18, L27, or a 2ᵏ⁻ᵖ) × outer array;
  - for each inner run, compute ȳ, s, ln s² and the **SN ratio**:
    - smaller-the-better: −10·log₁₀(Σy²/n);
    - larger-the-better: −10·log₁₀(Σ(1/y²)/n);
    - nominal-the-best: 10·log₁₀(ȳ²/s²);
  - main-effects plots for the SN ratio and the mean;
  - suggest settings: maximize SN, then use an adjustment factor (one that affects the mean but not SN) to reach the target;
  - show Montgomery's caveat and also fit separate models for ȳ and ln s².
- **Combined-array mode** (response-model approach):
  - one design over x and z;
  - fit y = β₀ + x′β + x′Bx + z′γ + x′Δz + ε;
  - derive the mean model E_z[y] = β₀ + x′β + x′Bx and the **variance model** Var_z[y] = σ_z²(γ + Δ′x)′(γ + Δ′x) + σ², where σ_z² is set by the user (default 1 in coded units) and σ² = MSE;
  - overlay contours of mean and SD;
  - optimizer: minimize Var subject to the mean being on target ± a tolerance.
- Highlight the significant **control × noise interactions**: they are what makes robustness possible.

### 8.5 DOE validation
Use the Montgomery examples in §12. Every effect estimate must match to 3 decimals.

---

## 9. Reports and code export

### 9.1 APA sentences (`report/apa.py`)
Use one template function per test. Rules from Meeting 4:
- italicize statistical symbols;
- give exact p to 3 decimals, and "p < .001" below that;
- drop the leading zero only for values that cannot exceed 1 (p, η², R², r);
- use df in parentheses;
- order: test → what was compared → assumption result → M and SD per group → statistic → effect size → follow-ups → meaning.

Sentences the templates must reproduce (golden strings; tested):
- "An independent samples t-test was conducted to compare … There was a significant difference in the scores for the experiment group (M = 51.5, SD = 11.0) and the control group (M = 41.5, SD = 17.1); t(42) = 2.267, p = .029, d = 0.684."
- RM with GG: "Since Mauchly's test indicated that the assumption of sphericity was violated, χ²(5) = 11.406, p = .047, and the Greenhouse-Geisser ε = 0.533, Greenhouse-Geisser correction was used. … F(1.599, 11.190) = 3.794, p = .063, η² = .351."
- Welch ANOVA: "Since Levene's test for equality of variances was significant, F(4, 129) = 2.607, p = .039, Welch ANOVA test was used. … F(4, 61.144) = 5.445, p < .001, η² = .114."
- Regression: "… F(1, 98) = 17.096, p < .001, R² = .149. BMI = 29.578 − 0.655 × PA …"
- Logistic: "… only the Intervention predictor had a significant effect (W(1) = 9.447, p = .002). Overall, the regression model was significant (χ²(111) = 9.926, p = .002), with R² = .084 (Cox & Snell). … the odds … are 3.42 times higher …"

### 9.2 Report document
A **Report** tab collects any cards the user pins: design summary, power, descriptives, assumptions, results, plots, APA text and interpretation. Export it to **PDF** (Playwright print, A4, with a header slot for name and student ID taken from Settings) and to standalone **HTML**.

### 9.3 Python code export
For every analysis, generate a runnable script using pandas, scipy, statsmodels and pingouin. The script reproduces the same numbers on the exported CSV. A test runs each generated script and compares its output with the API's.

---

## 10. API sketch
```
POST /api/tree/next            {answers} -> {node | outcome}
POST /api/power/{family}       {mode, params} -> {result, curve[]}
POST /api/analyze/{analysis_id}{data (records), roles {dv, factors_within, factors_between, covariates}, options} -> AnalysisResult
POST /api/doe/design           {type, factors, k, p|generators, replicates, center, seed} -> {runs[], alias, resolution}
POST /api/doe/analyze          {design, responses, model_terms} -> {effects, anova, plots}
POST /api/doe/rsm|robust       ...
POST /api/report/pdf           {cards[]} -> file
GET  /api/examples             -> list of §12 fixtures
```
`AnalysisResult` = `{tables[{title, columns, rows, footnotes}], plots[{plotly_json}], checks[], decisions[], effect_sizes[], apa, interpretation, python_code}`.
The frontend renders whatever it receives. Adding a test should never need UI code beyond registering its options form.

---

## 11. Quality bar
- **Numerical parity**: every table matches JASP to 3 decimals (G*Power: N must match exactly; power to 3 decimals). Where the libraries disagree with JASP (Type III SS, HF ε, Levene centering), follow JASP and record it in `docs/DECISIONS.md`.
- No silent switches: every automatic fallback shows up in the Decision log.
- Accessible: keyboard-navigable wizard, visible focus, color never the only signal (icons plus text on verdict chips).
- Works offline. Starts in under 3 seconds. A 10k-row CSV loads in under 1 second.

---

## 12. Validation suite (fixtures from the course)

Put these in `tests/fixtures/` and turn every expected number into a pytest assertion (tolerance 0.001 unless stated).

The student's project folder also holds the course's JASP files:
- `Montgomery Example 3.1 oneway ANOVA (independent sample) - data.jasp`
- `Montgomery Example 3.10 - data.jasp`
- `Montgomery Example 4.1 - data.jasp`
- `Montgomery Example 5.1 - data.jasp`
- `Example 6.2.jasp`
- `Example 6.2 if two replicates.jasp`
- `Example 8.1.jasp`
- `Example 8.2.jasp`

**Copy them into `tests/fixtures/jasp/`.** A `.jasp` file is a zip archive. Write `tests/tools/jasp_extract.py` to pull the data set (and the stored results, if present) out of each one as CSV plus JSON expected values, and add cases for them.

| # | Case | Data | Expected |
|---|---|---|---|
| 1 | Independent t, hand example (Meeting 4) | A = 6,7,8,9,10; B = 8,9,10,11,12 | t(8) = −2.000 (or 2.000 for B − A), p = .081, d = 1.265 |
| 2 | Independent t, DRP example (JASP Data Library "Directed Reading Activities") | Data Library file | t(42) = 2.267, p = .029, d = 0.684; M 51.48/41.52 |
| 3 | Two-way ANOVA, battery life (Montgomery Ex. 5.1) | Material 1: 15 °F 130,155,74,180 · 70 °F 34,40,80,75 · 125 °F 20,70,82,58. Material 2: 150,188,159,126 · 136,122,106,115 · 25,70,58,45. Material 3: 138,110,168,160 · 174,120,150,139 · 96,104,82,60 | SS: material 10,683.72 (F = 7.91, p = .0020); temperature 39,118.72 (F = 28.97); interaction 9,613.78 (F = 3.56, p = .0186); error 18,230.75, df 27 |
| 4 | 2⁴ filtration (Montgomery Ex. 6.2, Meeting 10) | (1) 45, a 71, b 48, ab 65, c 68, ac 60, bc 80, abc 65, d 43, ad 100, bd 45, abd 104, cd 75, acd 86, bcd 70, abcd 96 | Effects A 21.625, B 3.125, C 9.875, D 14.625, AC −18.125, AD 16.625, AB 0.125; SS(A) = 1870.56; A ≈ 32.6% contribution; after dropping B: a 2³ with 2 replicates, error df 8, F(A) = 83.36, F(AC) = 58.56, F(AD) = 49.27 |
| 5 | Half fraction 2⁴⁻¹, I = ABCD (Ex. 8.1) | runs (1) 45, ad 100, bd 45, ab 65, cd 75, ac 60, bc 80, abcd 96 | [A] = 19.00, [B] = 1.50, [C] = 14.00, [D] = 16.50, [AB] = −1.00, [AC] = −18.50, [AD] = 19.00; aliases A = BCD, AB = CD, AC = BD, AD = BC |
| 6 | Other half, I = −ABCD (Ex. 8.3) | d 43, a 71, b 48, abd 104, c 68, acd 86, bcd 70, abc 65 | [A]′ = 24.25, [B]′ = 4.75, [C]′ = 5.75, [D]′ = 12.75, [AB]′ = 1.25, [AC]′ = −17.75; combined halves = case 4 |
| 7 | Alias calculator (sample midterm C4) | I = −ABCDE | C → −ABDE; BCE → −AD; E = + when ABCD = (+ − + +); B = − when ACDE = (+ + − −) |
| 8 | Run counts | 2⁴, 2⁶⁻², 2⁵⁻¹, 2⁷⁻³ | 16, 16, 16, 16 |
| 9 | Logistic (Field, Meeting 14) | 56 untreated: 24 cured / 32 not; 57 treated: 41 / 16 | b₀ = −0.288, b = 1.229, SE = 0.400, OR = 3.417, Wald = 9.447, p = .002; deviance 154.1 → 144.2; Δχ² = 9.926; Cox & Snell R² = .084; M₀ intercept 0.303 |
| 10 | Logistic, Titanic (JASP Data Library) | Age + PClass | b: 2.034, −0.039, −1.146, −2.232; Δχ² = 115.656; Cox & Snell R² = .142 |
| 11 | Regression album sales (JASP Data Library, Field) | adverts → sales | sales = 134.14 + 0.096 × adverts; F(1, 198) = 99.587; hierarchical with airplay + attract: R² .335 → .665, ΔR² = .330, F change(3, 196) ≈ 129.5 (check df against JASP) |
| 12 | Power: independent t | d = .5, α = .05, power = .80, 2-tailed | n = 64 per group (N = 128) |
| 13 | Power: paired t | d_z = .5 | N = 34 |
| 14 | Power: one-way ANOVA | f = .25, k = 3 | N = 159 |
| 15 | Power: multiple regression | f² = .15, 3 predictors | N = 77 |
| 16 | Power: χ² | w = .3, df = 1 | N = 88 |
| 17 | Power: RM within | f = .25, 1 group, 3 measurements, ρ = .5, ε = 1 | N = 28 |
| 18 | Familywise error | 10 tests at .05 | 1 − .95¹⁰ = .401 |
| 19 | Latin square | n = 4 | every condition once per row and column; balanced (Williams) for even n |
| 20 | Decision tree | every path in `flowchart.json` | reaches the outcome shown on the HW3 chart |

### 12.1 Flagship end-to-end case: the group's candy choice-overload replication

This is real data from the student's group project, a classroom replication of Iyengar & Lepper (2000), *When choice is demotivating*, Study 3 (the chocolate study), using candy. Files are in `fixtures/candy/` next to this spec:
- `SYDE640_Real_Candy_Tasting_Questionnaire.xlsx`: questionnaires A and B, and the `DATA ENTRY` sheet;
- `2000-Iyengar_Lepper_choice_overload.pdf`: the original paper;
- `candy_clean.csv`: a cleaned version;
- `an.py`: the script that produced the expected numbers below.

Copy all four into `tests/fixtures/candy/`. Also ship the case as the **first course example** in the gallery, so it opens as a full project with the wizard answers already filled in.

**Design (what the wizard must conclude):**
- RQ: does a larger choice set (30 items) change difficulty, satisfaction, confidence, regret and decision time compared with a small set (6 items)?
- IV: **number of options**, a between-subject factor with 2 levels: Group A = 6 items (limited), Group B = 30 items (extensive). Each participant saw one display. Nominal.
- DVs:
  - Q1 difficulty, Q2 process satisfaction, Q3 confidence (before tasting);
  - Q4 satisfaction after tasting, Q5 regret, Q6 "should the display have included more kinds?";
  - all six are 1–7 ratings, so ordinal / treated as interval.
  - `Notes` is the **decision time in seconds** (the paper recorded time spent deciding). The importer must let the user rename the column and set its type. Participant 26 has no time value.
- Additional variables: `Made choice`, `Tasted` (Yes/No; values are mixed case, "yes"/"Yes", so they must be normalized), and `Selected item ID`.
- Expected wizard path: Lane A → 1 IV → 2 levels → between → **independent-samples t-test**, with Mann-Whitney U as the course fallback (Likert DVs, small n). It should also note that it is a quasi-random classroom sample.

**Expected behaviour.** n = 13 per group (time: A = 12, B = 13). Levene is mean-centered. Use the two-sided scipy Mann-Whitney U with continuity correction, which equals R's `wilcox.test` with ties. Pooled-SD Cohen's d is A − B.

| DV | A: M (SD) | B: M (SD) | Shapiro A / B | Levene p | Student t | Welch t | Mann-Whitney | d | App must… |
|---|---|---|---|---|---|---|---|---|---|
| Q1 difficulty | 1.923 (1.320) | 3.385 (1.710) | .002 / .269 | .245 | t(24) = −2.439, p = .022 | t(22.56) = −2.439, p = .023 | U = 40.5, p = .022 | −0.957 | flag non-normal A → **switch to Mann-Whitney**: significant, extensive choice was harder (consistent with the paper) |
| Q2 process satisfaction | 6.462 (0.877) | 5.923 (1.038) | <.001 / .001 | .799 | t(24) = 1.429, p = .166 | — | U = 117.0, p = .071 | 0.560 | switch to Mann-Whitney; not significant |
| Q3 confidence | 5.769 (1.235) | 6.077 (1.115) | .037 / .005 | .772 | t(24) = −0.667, p = .511 | — | U = 71.0, p = .482 | −0.261 | Mann-Whitney; not significant |
| Q4 satisfaction after tasting | 5.846 (1.573) | 6.385 (0.961) | .003 / .001 | .084 | t(24) = −1.053, p = .303 | t(19.86) = −1.053, p = .305 | U = 71.5, p = .474 | −0.413 | Mann-Whitney; not significant (the paper's lower satisfaction with extensive choice was **not** replicated, so the interpretation must say so) |
| Q5 regret | 2.077 (1.441) | 1.769 (1.363) | .002 / <.001 | .919 | t(24) = 0.559, p = .581 | — | U = 100.0, p = .390 | 0.219 | Mann-Whitney; not significant |
| Q6 wanted more kinds | 4.308 (1.494) | 2.308 (0.947) | .001 / .025 | .571 | t(24) = 4.077, p < .001 | t(20.31) = 4.077, p = .001 | U = 148.0, p = .001 | 1.599 | Mann-Whitney; significant, the limited group wanted more options |
| Decision time (s) | 7.236 (3.930), n = 12 | 18.501 (10.485) | .005 / .053 | **.001** | t(23) = −3.497, p = .002 | **t(15.54) = −3.609, p = .002** | U = 14.0, p = .001 | −1.400 | **both** assumptions fail → Mann-Whitney is primary (normality rule takes precedence); the Decision log also shows the Levene → Welch result; 1 missing value excluded and reported |

Rank-biserial r for the significant results: Q1 = −.521, Q6 = .751, time = −.821. The sign depends on the A − B direction, so state it in the output.

**Extra behaviour to test with this file:**
1. **Precedence rule.** When normality and equal variances both fail, use Mann-Whitney and mention Welch in the log. Record the rule in `DECISIONS.md`.
2. **Zero-variance warning.** Every participant made a choice and tasted. If the user tries a χ² test on "made a choice × group" (the paper's purchase-rate analysis), the app must say the outcome has no variation (all "Yes") and that the test cannot be run. It must not crash.
3. **Many DVs.** Seven t-tests on the same participants: show the familywise-α warning (1 − .95⁷ ≈ .30) and offer Bonferroni (α = .05/7 = .0071) or Holm. With Bonferroni, Q1 (p = .022) is no longer significant; Q6 and time stay significant.
4. **Power for the replication.**
   - Post hoc power for Q1 (d = 0.957, n = 13/13, α = .05, two-tailed) = **.649**.
   - A priori n per group for d = 0.957 at power .80 = **19**.
   - Sensitivity with 13/13 at power .80: minimum detectable d = **1.145**.
   - Decision time post hoc power (d = 1.400, n = 12/13) = **.917**.
   - The report should say the study was underpowered for medium effects.
5. **APA output.** Generate the paragraph for Q1 with the Mann-Whitney result. Expected shape: "A Mann-Whitney U test was conducted to compare decision difficulty between the limited-choice (6 items; Mdn = 1) and extensive-choice (30 items; Mdn = 3) groups. Difficulty was significantly higher with extensive choice, U = 40.5, p = .022, r = −.52."
6. **Paper comparison card.** For this example only, add a short "compared with Iyengar & Lepper (2000)" note: which effects were replicated (difficulty, decision time) and which were not (satisfaction, regret).

Cases 12–17 are the standard G*Power 3.1 results. If the engine disagrees by more than ±1, compare against the G*Power desktop app before changing the code.

UI end-to-end tests (Playwright): for cases 3, 4 and 9, walk the wizard from Home to the APA paragraph, entering the answers and pasting the data.

---

## 13. Build plan (phases)

1. **Skeleton**: repo, `run.py`, FastAPI + Vite shell, theme, Home screen, project save/load (`.dlab`).
2. **Data grid**: import, paste, typing, reshaping, validation.
3. **Lane A engine + results UI**: t-tests, one-way, RM, factorial, mixed, assumptions, fallbacks, post hoc tests, simple main effects, APA. Cases 1–3 pass.
4. **Wizard**: `flowchart.json`, decision engine, left rail, live recommendation, "Not sure?" helpers, design summary, data template. Case 20 passes.
5. **Power module**: all families, modes and curves; wired into the wizard. Cases 12–18 pass.
6. **Lanes B and C**: regression (all entry methods, diagnostics), logistic, χ². Cases 9–11 pass.
7. **Lane D**: 2ᵏ, fractional (aliases, fold-over), RSM, robust design. Cases 4–8 pass.
8. **Reports**: Report tab, PDF/HTML export, Python code export with round-trip tests.
9. **Polish**: Learn mode hover cards, course-examples gallery, dark mode, accessibility, end-to-end tests, README with screenshots.

Definition of done: every phase's validation cases pass, `python run.py` works on a clean machine after `pip install -r requirements.txt` and `npm ci && npm run build`, and the README explains installation in 5 steps or fewer.

---

## 14. Course content to embed (help text and Learn mode)
Use these facts word for word in the help texts; they come from the lectures.
- **Experiment**: "a test designed to objectively observe phenomena which are made to occur in a strictly controlled situation where one or more variables are varied, and the others are held constant." (Meeting 1)
- **The 10 research steps**: RQ → hypotheses → variables and measurements → control → statistical test → sample size → ethics → data collection → analysis → report.
- **Within vs between**: within gives fewer people, removes individual differences and has more power, but risks carryover (practice, fatigue). Counterbalancing *controls* carryover. If learning effects are large and hard to counterbalance, use between.
- **Type I** = false positive (α, p). **Type II** = false negative (β). Power = 1 − β. Significance ≠ magnitude, so report effect sizes. Box plot line = median.
- **Cohen's d** .2 / .5 / .8. **f²** .02 / .15 / .35. η² = SS_between / SS_total.
- **Polynomial contrasts**: linear = straight line; quadratic = 1 bend; cubic = 2 bends.
- **RM ANOVA**: subject SS is removed from the error term. Sphericity rule ε < 0.60 → GG, else HF. Friedman + Conover when normality fails. Block design = within-subject in engineering terms.
- **Mixed design**: sphericity applies to the within factors, homogeneity of variance to the between factors.
- **2ᵏ designs** are for screening (early engineering, linear effects), not for finding causal mechanisms. Fractional designs: judge by effect size; they work best when within-condition variation is small.
- **Regression**: B = original units, β = compare predictors; VIF < 10; Cook's D > 1 = influential case; forward entry = highest simple correlation first, then the largest semi-partial correlation.
- **Logistic**: the odds ratio multiplies the *odds*, not the probability. k levels → k − 1 dummies.
- **APA rules** (§9.1).

The HW3 flow chart PDF is the visual and logical reference for all of the above.
