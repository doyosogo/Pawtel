# Payment interview notes

1. **Why Checkout Sessions?** Stripe owns card collection/authentication/lifecycle;
   Elements lets a later React UI keep PAWTEL's design without raw card orchestration.
2. **Idempotency vs deduplication?** A stable request key prevents repeated provider
   side effects; a unique Event ID prevents applying one webhook delivery twice.
3. **Why duplicate webhooks?** Delivery is retry-based across unreliable networks;
   PAWTEL must tolerate successful processing followed by a lost acknowledgement.
4. **Why not assume event order?** Delivery/retries race. Validate current local state
   and provider identity instead of sorting by event timestamps.
5. **Why raw-body signatures?** The signature authenticates the original bytes;
   parsing/re-serializing JSON changes those bytes even if the data looks equivalent.
6. **Why is a redirect insufficient?** A browser is untrusted, can spoof navigation,
   or close before return. A validated provider webhook is the confirmation authority.
7. **How without distributed transactions?** Commit attempt identity, call provider
   with its fixed key, then commit returned IDs. Retry recovers the same operation.
8. **What if a timeout hides success?** Keep CREATING/unknown outcome; reuse the same
   parameters/key rather than inventing another attempt or claiming definite failure.
9. **Why protect client secrets?** They permit client-side Checkout operations. Return
   only to the Owner; never store/log them or put them in URLs/browser persistence.
10. **What about cancellation/payment races?** Cancel/release under the shared lock;
    expire provider outside it. Late paid success becomes reconciliation, not revival.
11. **Why sticky reconciliation?** Real money must not disappear from local attention
    because an older expiry arrives later. Refund/manual investigation remains explicit.
12. **Why no provider calls while locked?** Network delay/failure would block inventory
    writers yet still cannot make Stripe and PostgreSQL one transaction.
13. **Why refresh ORM rows?** Another transaction's webhook may already have completed
    payment. A cached CREATING object must not overwrite that newer locked row state.
14. **Why is failed card not PAYMENT_FAILED?** The Checkout can remain open for retry;
    only supported terminal provider facts affect Booking state in this integration.
15. **Does confirmation consume new capacity?** No. AWAITING_PAYMENT already reserved
    it; CONFIRMED preserves the hold. Expiry/cancellation release under Listing locking.
16. **Why no queue yet?** Webhooks perform short SQL mutations. Add asynchronous
    infrastructure only when workload/latency measurements justify its failure modes.
