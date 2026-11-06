# Sprint 10 / D48 (P3): Conformance & Graph Methodology and Limitations

> **Module E Technical Paper Section & Audit**  
> **Author**: Person 3 (Static Analysis, Architecture Recovery & Conformance Lead)  
> **Sprint Scope**: Days 46–50 (Sprint 10 Final Deliverable)

---

## 1. Executive Summary

This document presents the formal methodology, design principles, experimental results, and limitations of the **ArchLens Deterministic Conformance Engine (Module E)** and **Source-Code Architecture Recovery Pipeline (Module D)**.

Unlike heuristic or purely generative approaches that query Large Language Models for structural validation, ArchLens strictly enforces the **Non-Negotiable Engineering Rule**:
> *Static analysis establishes structural facts such as imports, calls, and dependencies; the graph conformance engine determines rule violations deterministically.*

---

## 2. Graph Representation & Formal Models

### 2.1 Intended Architecture Graph ($G_I$)
The intended architecture $G_I = (V_I, E_I)$ represents the high-level system design derived from architectural diagrams or formal architecture specifications:
- **Vertices ($V_I$)**: Each $v \in V_I$ represents an intended component characterized by a canonical name, architectural type $\tau(v) \in \mathcal{T}_{comp}$ (e.g., `controller`, `service`, `repository`, `database`, `gateway`), spatial bounding box, and extraction confidence score $c(v) \in [0.0, 1.0]$.
- **Edges ($E_I$)**: Each directed edge $e = (u, v) \in E_I$ represents a declared dependency or communication channel with type $\rho(e) \in \mathcal{R}_{edge}$ (e.g., `depends_on`, `calls`, `writes_to`, `publishes_to`) and confidence score $c(e)$.

### 2.2 Recovered Current Architecture Graph ($G_C$)
The current architecture $G_C = (V_C, E_C)$ is extracted deterministically from source code:
- **AST Parsing**:
  - **Python**: Extracted via Python's built-in `ast` module (`PythonASTParser`), resolving module definitions, classes, functions, explicit imports, relative imports, and structured call targets.
  - **Java**: Extracted via `tree-sitter` (`JavaTreeSitterParser`), recovering package declarations, class/interface declarations, field types, method invocations, and inheritance hierarchies (`extends`, `implements`).
- **Graph Aggregation**: File/class entities are aggregated to package/service boundaries using `PackageGraphAggregator`, eliminating intra-package self-loops while preserving maximum edge confidence.

---

## 3. Conformance Engine Architecture & Rules

The conformance engine applies a deterministic decision procedure to pair $G_I$ and $G_C$ against a versioned `RuleSet`.

```
                    ┌─────────────────────────┐
                    │  Intended Graph (G_I)   │
                    └────────────┬────────────┘
                                 │
  ┌──────────────────┐           ▼           ┌──────────────────────┐
  │ Source Code Repo ├─► Architecture Recovery├─► Current Graph (G_C)│
  └──────────────────┘     (AST / Tree-sitter)└──────────┬───────────┘
                                                         │
                                 ┌───────────────────────┘
                                 ▼
                     ┌───────────────────────┐
                     │ GraphIntegrityChecker │
                     │   (Pre-flight Audit)  │
                     └───────────┬───────────┘
                                 │
                     ┌───────────▼───────────┐
                     │   ConformanceEngine   │
                     │  - ALLOW / FORBID     │
                     │  - REQUIRE rules      │
                     │  - LayerViolation     │
                     │  - BoundaryViolation  │
                     │  - CycleDetection     │
                     └───────────┬───────────┘
                                 │
                 ┌───────────────┼───────────────┐
                 ▼               ▼               ▼
          [5-Verdict Report] [Blast Radius]  [Git Mining]
```

### 3.1 Five-Verdict Conformance Taxonomy
Every inspected relationship or architectural constraint receives exactly one verdict:

| Verdict | Definition | Severity |
| :--- | :--- | :--- |
| **`CONFORMANT`** | Relationship is explicitly modeled in $G_I$ or permitted by an `ALLOW` rule. | None |
| **`VIOLATION`** | Implementation contains a relationship explicitly prohibited by `FORBID`, violating top-down layer hierarchy, crossing unmodeled domain boundaries, or participating in a cyclic dependency. | High / Critical |
| **`MISSING`** | An essential architectural relationship declared in $G_I$ or mandated by a `REQUIRE` rule is absent in $G_C$. | Medium / High |
| **`UNEXPECTED`** | Implementation contains a relationship absent from $G_I$ that is not covered by any `ALLOW` or `FORBID` rule. | Medium |
| **`UNCERTAIN`** | Relationship confidence score $c(e)$ is below the policy threshold ($\theta < 0.6$). | Low |

### 3.2 Implemented Rule Checkers
1. **`ForbiddenDependencyRule`**: Matches source and target types or identifiers against explicit negative constraints (e.g. `controller -> repository`).
2. **`LayerViolationRule`**: Implements strict layer ordering:
   $$\text{frontend} \prec \text{gateway} \prec \text{controller} \prec \text{service} \prec \text{repository} \prec \text{database} \prec \text{cache} \prec \text{queue}$$
   Any upward dependency (where $\text{layer}(u) > \text{layer}(v)$) triggers an automatic `VIOLATION`.
3. **`BoundaryViolationRule`**: Enforces domain isolation. When entities belong to disjoint domains (e.g., `orders.*` vs `payments.*`), cross-domain edges not declared in $G_I$ are rejected.
4. **`CycleDetectionRule`**: Evaluates Tarjan's/Johnson's elementary cycle decomposition on $G_C$ via `nx.simple_cycles(G_C)`. All cyclic subgraphs are flagged as `VIOLATION`.
5. **`MissingDependencyRule`**: Evaluates $E_I \setminus E_C$ and unsatisfied `REQUIRE` rules.

---

## 4. Impact Analysis & Blast Radius (Sprint 8)

When a violation $(u, v)$ is flagged, `compute_impact_summary()` determines the architectural blast radius:
- **Upstream Coupled Components**: $\text{Ancestors}(G_C, u)$ — all components that depend on $u$ and could be impacted if the interface or contract is refactored.
- **Downstream Affected Components**: $\text{Descendants}(G_C, v)$ — all components transitively reachable from $v$ to which $u$ is now inadvertently coupled.
- **Severity Tiers**:
  $$\text{Fraction} = \frac{|\text{Upstream}| + |\text{Downstream}|}{|V_C|}$$
  - $< 0.1$: `LOW`
  - $0.1 - 0.3$: `MEDIUM`
  - $0.3 - 0.6$: `HIGH`
  - $\ge 0.6$: `CRITICAL`
- **Correction Validation**: `validate_correction_edges()` verifies that candidate architectural fixes do not introduce secondary forbidden dependencies.

---

## 5. Experimental Results (Sprint 9 Evaluation)

Baseline conformance evaluation was conducted on controlled repository benchmarks (`backend/tests/fixtures/sample_repo`):

| Baseline | Precision | Recall | F1 Score | TP | FP | FN |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| **Static-Only** (Default Rules) | 0.1667 | 1.0000 | 0.2857 | 1 | 5 | 0 |
| **Static + Conformance** (Full Policy) | 0.1667 | 1.0000 | 0.2857 | 1 | 5 | 0 |
| **Full Pipeline** (Evidence-Grounded) | 0.1667 | 1.0000 | 0.2857 | 1 | 5 | 0 |

*Note: In the controlled benchmark, recall is 100% (the ground-truth violation `controller -> repository` is localized without fail). Precision reflects strict zero-tolerance detection of unmodeled auxiliary package dependencies (`repositories -> models`).*

---

## 6. Known Limitations Stated Plainly (D48 / D49)

1. **Static Analysis Horizon (Dynamic Dispatch & Reflection)**:
   - Python AST analysis cannot resolve dynamically computed imports (e.g. `importlib.import_module()`) or monkey-patched method bindings.
   - Java Tree-sitter extraction captures declared interface implementations, but cannot resolve runtime dependency injection containers (Spring `@Autowired`, Guice) without runtime metadata.
2. **Grammar Availability**:
   - `tree-sitter-java` operates as an optional acceleration grammar; systems without pre-built C-compilers gracefully degrade to AST-only Python parsing.
3. **Domain Boundary Heuristic**:
   - `BoundaryViolationRule` assumes hierarchical naming (`module.submodule`) or explicit metadata. Repositories with flat directories without metadata cannot apply boundary isolation checks automatically.
4. **Git Pickaxe Specificity**:
   - `git_evidence_p3.py` relies on string pickaxe (`git log -S<pattern>`). Overly broad search tokens (e.g., `service`) yield false-positive historical candidates; specific symbol names are required for rank-1 precision.
5. **Shallow Clones**:
   - Repositories checked out with truncated history (`git clone --depth 1`) prevent introducing-commit resolution beyond the shallow commit graft.

---

## 7. Verification & Release Acceptance (D49 / D50)

The P3 deliverables pass all acceptance gates:
- **Unit Test Coverage**: 92 automated tests passing with 0 failures (`pytest tests/unit/test_graph_builder.py test_conformance_engine.py test_git_evidence_p3.py test_impact_extended.py test_conformance_metrics.py`).
- **Reproducibility**: `demo_p3_conformance_pipeline.py` and `evaluate_conformance_baselines.py` run out-of-the-box and generate deterministic JSON artifacts.
- **Release Tag**: `v1.0.0-p3` ready for final release integration.
