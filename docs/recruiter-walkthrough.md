# Explore PAWTEL in two minutes

Open [the live frontend showcase](https://pawtel-ashen.vercel.app/). It uses the
actual React interface with **synthetic data and simulated actions**. No
passwords, backend setup, real accounts, reservations or payments are required
or created.

1. Search **Glenelg** and open **Coastal calm for little companions**.
2. Choose **Explore as Owner** in the showcase bar; inspect Milo and Luna in My
   Pets.
3. Use **Find a stay** to return to the Glenelg Listing. Choose future check-in
   and checkout dates, select Milo and choose **Request booking**.
4. The detail page shows **Waiting for the Host to respond**. Switch using
   **Explore as Host**, then **Open booking inbox**.
5. Open your newest request (match its dates) and choose **Accept request**.
6. Switch back to Owner. In **Account menu → My Bookings**, open the same
   request: it now shows **Payment required**.
7. **Pay securely** shows an explicitly disabled Stripe preview; it requests no
   card details. **Reset showcase** restores the starting examples. Refresh also
   resets memory, so use the app's links during the journey.

For the engineering behind the real implementation, start with
[architecture](architecture.md), [Booking concurrency](bookings.md),
[payments](payments.md) and [CI/test operations](operations.md). The
[README](../README.md) links the current green GitHub run and verified test
counts.

The Vercel site demonstrates interface exploration, not server security or
durable transactions. Those are separately implemented/tested in React → FastAPI
→ PostgreSQL. The full-stack Render demo is not live; see the
[showcase boundary and hosted evidence](frontend-showcase.md).
