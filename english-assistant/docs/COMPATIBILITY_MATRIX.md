# Supported-App Compatibility Matrix

**Filled in during Phase 5.** In Phase 0 this is an empty template so the owner can
see exactly what will be measured per app. Because third-party apps change, every
row is expected to shift over time — that is normal.

> We will **never** use hardcoded screen coordinates and **never** identify Send
> buttons for automated clicking.

## Template (one table per app, repeated for TikTok / Instagram / Facebook / Messenger)

| Question | Result | Notes |
|----------|--------|-------|
| Can selected text be retrieved? | _TBD Phase 5_ | |
| Can the focused input field be found? | _TBD_ | |
| Does `ACTION_SET_TEXT` work? | _TBD_ | |
| Is clipboard fallback needed? | _TBD_ | |
| Which accessibility event types are observed? | _TBD_ | |
| What limitations exist? | _TBD_ | |
| What changed after the last app update? | _TBD_ | |
| App version tested | _TBD_ | |
| Android version(s) tested | _TBD_ | |

### TikTok (`com.zhiliaoapp.musically`)
_Pending Phase 5._ (Known risk: heavy custom rendering may expose few readable
nodes — expect frequent fallback use.)

### Instagram (`com.instagram.android`)
_Pending Phase 5._

### Facebook (`com.facebook.katana`)
_Pending Phase 5._

### Messenger (`com.facebook.orca`)
_Pending Phase 5._

## Summary matrix (to complete)

| App | Read message | Find input | Set text | Fallback needed | Overall |
|-----|-------------|-----------|----------|-----------------|---------|
| TikTok | – | – | – | – | – |
| Instagram | – | – | – | – | – |
| Facebook | – | – | – | – | – |
| Messenger | – | – | – | – | – |
