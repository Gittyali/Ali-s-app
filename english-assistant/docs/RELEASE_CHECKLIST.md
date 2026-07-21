# Release Checklist

**Completed in Phase 7.** Listed now so the owner sees the finish line. Nothing here
promises Google Play approval — `AccessibilityService` compliance is reviewed before
publication and approval is at Google's discretion.

## Build
- [ ] Signed release build instructions written for a beginner (exact commands).
- [ ] APK build command documented.
- [ ] App Bundle (AAB) build command documented.
- [ ] Release signing key created and safely backed up (never committed).
- [ ] `usesCleartextTraffic=false` verified; Network Security Config in place.
- [ ] No secrets in APK/AAB (secret scan clean).

## Play Console
- [ ] Accessibility declaration completed truthfully.
- [ ] Data Safety form completed (per `PRIVACY.md`).
- [ ] Privacy policy URL published.
- [ ] Prominent-disclosure screen matches declaration (`ACCESSIBILITY_POLICY.md`).
- [ ] Reviewer access / demonstration instructions prepared.
- [ ] Store listing draft (Urdu-first) written.
- [ ] Urdu onboarding screenshots captured per checklist.
- [ ] Closed-testing track plan documented.

## Safety & ops
- [ ] Crash reporting configured to **exclude** message content.
- [ ] Rollback plan documented.
- [ ] Final security + privacy audit (Phase 6) signed off.
- [ ] Compatibility matrix (Phase 5) attached.

## Fallback
- [ ] Personal sideload APK path documented in case store approval is refused.
