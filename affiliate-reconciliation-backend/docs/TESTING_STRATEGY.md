# Testing Strategy

How we ensure correctness, resilience, and regression detection across the reconciliation platform.

## 1. Philosophy
| Principle | Implementation |
|-----------|---------------|
| Fast feedback | Unit & classification logic tests run in <1s each |
| Behavior over implementation | Integration & full system tests exercise API + worker, not internal calls |
| Determinism | Adapter patching replaces external variability |
| Isolation | Queue purge + circuit breaker reset autouse fixture |
| Representative risk paths | Overclaim, partial, missing, retry, alert escalation, trust evolution all covered |

## 2. Test Pyramid
| Layer | Files (Examples) | Focus |
|-------|------------------|-------|
| Unit | `test_unit_*` (queue, circuit_breaker, discrepancy_classifier, trust_scoring, backoff) | Pure functions & data structures |
| Integration | `test_integration_reconciliation.py` | Status classification, trust, alert creation w/o real external APIs (worker replaced before refactor → now worker path adopted) |
| API Edge Cases | `test_edge_cases.py` | Conflicts, platform not in campaign, alert resolution API |
| End-to-End (Scenario) | `test_full_system.py` | Sequential multi-status journey & trust/alert assertions through queue + worker |
| RBAC & Uniqueness | `test_rbac_and_uniqueness.py` | Uniqueness constraints, duplicate submissions |
| E2E Legacy | `test_e2e_flow.py` | Earlier black-box flow (kept for redundancy) |

## 3. Deterministic Adapter Patching
All platform metrics sourced via `install_mock_adapter("reddit", {...})` which monkeypatches `fetch_post_metrics` in `app.integrations.<platform>`.
| Benefit | Detail |
|---------|-------|
| No network flakiness | Synchronous stub returns fixed dict or raises exception |
| Scenario shaping | Force partial (None values) or missing (raise) |
| Repeatability | Same inputs yield identical classification & trust deltas |

## 4. Isolation Mechanics
Autouse fixture (`_isolate_test_state`) performs:
- Queue purge: removes residual jobs.
- Circuit breaker state clear: prevents cross-test open circuit causing false missing statuses.
- Distinct affiliates & posts per test to avoid uniqueness collisions.

## 5. Worker vs Direct Engine Calls
Originally, integration tests invoked `run_reconciliation` directly (faster, deterministic). Updated strategy prefers **worker-driven** path to:
- Validate queue enqueue + worker consumption.
- Surface threading / session binding issues early.
- Mirror production black-box flow.
Remaining direct calls noted as legacy but minimized.

## 6. Coverage of Core Requirements
| Requirement | Test(s) |
|------------|---------|
| Perfect match trust increase | Full system & trust evolution integration |
| Overclaim classification & alert | Full system, overclaim integration test |
| High discrepancy & escalation | High discrepancy repeat scenario test |
| Partial data handling | Partial/incomplete specific test & full system step D |
| Missing data retry scheduling | Missing data integration test & full system step E |
| Alert resolution API | `test_alert_resolution_flow` |
| Queue priority basic functionality | Unit priority queue test |
| Circuit breaker open logic | Unit circuit breaker test; implicit via isolation fixture |

## 7. Edge Cases Explicitly Tested
| Edge Case | Validation |
|-----------|-----------|
| Duplicate affiliate email | Conflict status code |
| Duplicate post submission | 409 conflict test |
| Platform not in campaign submission | 400 bad request test |
| Trust monotonic ordering across scenarios | Full system test final assertions |
| Missing vs incomplete classification divergence | Specific integration tests |

## 8. Gaps / Future Test Additions
| Gap | Planned Test |
|-----|-------------|
| Rate limit handling | Simulate adapter raising rate limit specific message; assert rate_limited flag |
| Auth error terminal | Simulate auth error -> ensure no retry scheduled |
| Retry schedule math correctness | Parameterized test verifying minute offsets for attempts 1..N |
| Duplicate job idempotency | Enqueue same report twice; assert single trust delta |
| Circuit breaker half-open probe behavior | Force rapid failures then success probe |

## 9. Performance Considerations
- Backoff sleeps in PlatformFetcher are real (`time.sleep`); tests controlling retries keep attempts minimal to stay fast.
- Full system test runtime ~5s due to intentional fast polling + single worker.
- Potential optimization: monkeypatch backoff function to zero delay in test profile (not yet required).

## 10. Testing Utilities
| Utility | Purpose |
|---------|--------|
| `wait_for(predicate)` | Poll until reconciliation log exists / status reached |
| Adapter patch installers | Deterministic metrics & failure injection |
| Factory fixtures (platform, affiliate, campaign) | Concise entity creation with uniqueness safeguards |

## 11. Sample Assertion Patterns
```python
log = wait_for(lambda: session.query(ReconciliationLog).filter_by(affiliate_report_id=rid).first())
assert log.status == ReconciliationStatus.DISCREPANCY_MEDIUM
assert float(affiliate.trust_score) < previous_trust
```

## 12. Flakiness Mitigation Choices
| Issue | Mitigation |
|-------|-----------|
| Threaded DB session mismatch | Switched to file-based SQLite | 
| Circuit breaker leakage across tests | Autouse reset fixture |
| Timing race for reconciliation log | Polling utility with timeout |

## 13. Guidelines for New Tests
1. Prefer black-box (API + worker) unless measuring pure function logic.
2. Use adapter patch, not direct metric injection into DB.
3. Avoid asserting exact trust score floating points after multiple deltas if config may change— assert relative ordering.
4. Keep test names descriptive (scenario + expected outcome).
5. Add fixtures instead of duplicating object construction boilerplate.

## 14. Local Developer Workflow
```
# Run fast unit layer
pytest tests/test_unit_*.py -q

# Run integration & full system only
pytest tests/test_integration_reconciliation.py tests/test_full_system.py -q

# Full regression
pytest -q
```

## 15. Continuous Improvement Backlog
| Improvement | Value |
|------------|-------|
| Coverage report integration (pytest-cov) | Quantify gaps |
| Property-based tests for classifier | Stress boundary conditions |
| Synthetic load test harness | Measure queue saturation behavior |
| Mutation testing (e.g., mutmut) | Detect assertion weakness |

---
Next: `OPERATIONS_AND_OBSERVABILITY.md`.
