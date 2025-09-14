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
| Layer | Files | Focus | Runtime |
|-------|-------|-------|---------|
| Unit | `test_unit_*` (backoff, circuit_breaker, discrepancy_classifier, priority_queue, trust_scoring) | Pure functions & data structures | <1s each |
| Integration | `test_integration_reconciliation.py` | Status classification, trust, alert creation with mocked adapters | ~2-3s |
| API Edge Cases | `test_edge_cases.py` | Conflicts, platform validation, alert resolution API | ~1-2s |
| End-to-End | `test_full_system.py` | Sequential multi-status journey through queue + worker | ~5s |
| RBAC & Auth | `test_rbac_and_uniqueness.py`, `test_bot_token_auth.py` | Authentication, uniqueness constraints, duplicate submissions | ~1-2s |
| Legacy E2E | `test_e2e_flow.py` | Earlier black-box flow (maintained for redundancy) | ~3-4s |

## 3. Deterministic Adapter Patching
All platform metrics sourced via `install_mock_adapter("reddit", {...})` which monkeypatches `fetch_post_metrics` in `app.integrations.<platform>`.
| Benefit | Detail |
|---------|-------|
| No network flakiness | Synchronous stub returns fixed dict or raises exception |
| Scenario shaping | Force partial (None values) or missing (raise) |
| Repeatability | Same inputs yield identical classification & trust deltas |

## 4. Isolation Mechanics
Autouse fixture (`_isolate_test_state`) in `conftest.py` performs:
- **Queue purge**: Removes residual jobs between tests using `queue.purge()`
- **Circuit breaker reset**: Clears failure counters and state with `GLOBAL_CIRCUIT_BREAKER._states.clear()`
- **Database isolation**: Uses file-based SQLite (`test_worker.db`) for thread-safe multi-connection access
- **Session rebinding**: Replaces `SessionLocal` in both app and worker modules to use test database
- **Worker thread**: Starts daemon worker thread that processes jobs from test queue

**Pre/post-test cleanup**: Ensures no cross-test contamination of in-memory state.

## 5. Worker vs Direct Engine Calls
**Current Strategy**: Tests prefer **worker-driven** path to validate end-to-end flow:
- Full API request → queue enqueue → worker consumption → reconciliation processing
- Validates threading, session binding, and production-like execution path
- Surfaces integration issues early (database sessions, queue timing, etc.)

**Legacy Direct Calls**: Some integration tests still use `run_reconciliation()` directly:
- Faster execution for focused logic testing
- Used in `test_integration_reconciliation.py` for specific scenarios
- Gradually being migrated to full worker path for consistency

**Test Database**: Uses file-based SQLite (`test_worker.db`) to support:
- Multi-threaded access (test thread + worker thread)
- Session sharing between API calls and background processing
- Automatic cleanup between test runs

## 6. Coverage of Core Requirements
| Requirement | Test Coverage | Files |
|------------|----------------|-------|
| Multi-platform integrations | Mock adapters for Reddit, Instagram, Meta | `test_full_system.py`, `test_integration_reconciliation.py` |
| Discord affiliate reporting | Bot token authentication | `test_bot_token_auth.py` |
| Direct API affiliate reporting | API key authentication, submission validation | `test_rbac_and_uniqueness.py`, `test_edge_cases.py` |
| Automated reconciliation | Queue + worker processing | `test_full_system.py` |
| Discrepancy detection | Classification algorithm, trust scoring | `test_unit_discrepancy_classifier.py`, `test_full_system.py` |
| Alert mechanism | Configurable thresholds, severity levels | `test_full_system.py`, `test_integration_reconciliation.py` |
| Data quality validation | Duplicate detection, input sanitization | `test_edge_cases.py`, `test_rbac_and_uniqueness.py` |

## 7. Edge Cases Explicitly Tested
| Edge Case | Test Coverage | Files |
|-----------|----------------|-------|
| Duplicate affiliate email | Uniqueness constraint validation | `test_rbac_and_uniqueness.py` |
| Duplicate post submission | 409 conflict response | `test_edge_cases.py` |
| Platform not in campaign | 400 bad request validation | `test_edge_cases.py` |
| Trust score progression | Monotonic ordering across scenarios | `test_full_system.py` |
| Missing vs partial data | Classification divergence | `test_integration_reconciliation.py` |
| Overclaim detection | Significant affiliate inflation | `test_full_system.py` |
| Circuit breaker behavior | Failure threshold and recovery | `test_unit_circuit_breaker.py` |
| Queue priority ordering | Lower numeric = higher priority | `test_unit_priority_queue.py` |
| Discord bot authentication | Token validation and permissions | `test_bot_token_auth.py` |

## 8. Future Test Enhancements
| Enhancement | Rationale | Priority |
|-------------|-----------|----------|
| Rate limit handling tests | Simulate platform rate limiting scenarios | P2 |
| Auth error terminal tests | Test authentication failure handling | P2 |
| Retry backoff validation | Verify exponential backoff timing | P2 |
| Duplicate job idempotency | Ensure no double trust deltas | P2 |
| Circuit breaker half-open tests | Test recovery behavior | P2 |
| Performance/load testing | Measure throughput under load | P3 |
| Multi-platform concurrent tests | Test cross-platform scenarios | P3 |

## 9. Performance Considerations
- **Unit tests**: <1s each, pure function testing
- **Integration tests**: ~2-3s, includes database operations and worker processing
- **Full system test**: ~5s due to intentional polling (`POLL_INTERVAL = 0.05`, `TIMEOUT = 4.0`)
- **Database**: File-based SQLite (`test_worker.db`) for thread-safe multi-connection access
- **Cleanup**: Automatic database creation/dropping between test sessions
- **Isolation**: Pre/post-test cleanup prevents cross-test contamination

**Optimization Notes**: 
- Backoff sleeps in PlatformFetcher use real `time.sleep()` but are minimal in test scenarios
- No need for monkeypatching delays as test scenarios complete quickly
- Full test suite runs in ~15-20 seconds on typical development hardware

## 10. Testing Utilities
| Utility | Purpose | Location |
|---------|---------|----------|
| `wait_for(predicate)` | Poll until condition met (reconciliation complete, etc.) | `test_full_system.py` |
| `install_mock_adapter()` | Deterministic metrics & failure injection for platform adapters | `test_full_system.py` |
| `platform_factory` | Create platform entities with uniqueness safeguards | `conftest.py` |
| `affiliate_factory` | Create affiliate users with unique names/emails | `conftest.py` |
| `campaign_factory` | Create campaigns with platform associations | `conftest.py` |
| `auth_header` | Generate authentication headers for API tests | `conftest.py` |
| `client` | FastAPI TestClient for API testing | `conftest.py` |
| `db_session` | SQLAlchemy session for database operations | `conftest.py` |
| `reconciliation_queue` | Priority queue instance for testing | `conftest.py` |

## 11. Sample Assertion Patterns
```python
log = wait_for(lambda: session.query(ReconciliationLog).filter_by(affiliate_report_id=rid).first())
assert log.status == ReconciliationStatus.DISCREPANCY_MEDIUM
assert float(affiliate.trust_score) < previous_trust
```

## 12. Flakiness Mitigation Choices
| Issue | Mitigation | Implementation |
|-------|-----------|----------------|
| Threaded DB session conflicts | File-based SQLite with `check_same_thread=False` | `test_worker.db` for multi-threaded access |
| Circuit breaker leakage | Autouse reset fixture | `GLOBAL_CIRCUIT_BREAKER._states.clear()` |
| Timing race for reconciliation log | Polling utility with timeout | `wait_for()` with configurable timeout |
| Queue state contamination | Pre/post-test purge | `queue.purge()` in isolation fixture |
| Session binding issues | Dynamic SessionLocal rebinding | Replaces `SessionLocal` in app and worker modules |

## 13. Guidelines for New Tests
1. **Prefer black-box testing**: Use API + worker path unless testing pure functions
2. **Use factory fixtures**: Leverage `platform_factory`, `affiliate_factory`, `campaign_factory` for consistent test data
3. **Mock at adapter level**: Use `install_mock_adapter()` for deterministic platform responses
4. **Test realistic scenarios**: Focus on actual user journeys and edge cases
5. **Assert meaningful outcomes**: Check status, trust changes, alerts, retries - not just implementation details
6. **Keep tests focused**: One scenario per test, clear naming (scenario + expected outcome)
7. **Handle async operations**: Use `wait_for()` for reconciliation completion
8. **Test isolation**: Rely on autouse fixtures for automatic cleanup
9. **Document complex scenarios**: Add comments explaining test setup and assertions
10. **Performance matters**: Keep individual tests fast, full suite under 30 seconds

## 14. Local Developer Workflow
```bash
# Quick unit test run (fast feedback)
poetry run pytest tests/test_unit_*.py -q

# Integration tests only
poetry run pytest tests/test_integration_reconciliation.py -q

# Full system end-to-end test
poetry run pytest tests/test_full_system.py -q

# All tests with coverage
poetry run pytest --cov=app --cov-report=html

# Run specific test file
poetry run pytest tests/test_edge_cases.py -v

# Run tests matching pattern
poetry run pytest -k "test_full_system_flow" -v

# Debug mode (stop on first failure)
poetry run pytest -x --pdb
```

**Test Database**: Tests use `test_worker.db` (file-based SQLite) for thread-safe operations. Database is automatically created/dropped between test sessions.

## 15. Continuous Improvement Backlog
| Improvement | Value | Priority |
|------------|-------|----------|
| Coverage reporting integration | Quantify test gaps with coverage metrics | P2 |
| Property-based testing | Stress test edge cases with generated inputs | P3 |
| Test performance optimization | Reduce full test suite runtime | P2 |
| Mutation testing | Detect weak assertions (mutmut or similar) | P3 |
| Visual test reporting | HTML reports with failure screenshots | P2 |
| CI/CD integration | Automated testing in deployment pipeline | P1 |

---
Next: `OPERATIONS_AND_OBSERVABILITY.md`.
