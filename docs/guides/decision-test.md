# Test the updated decision flow in your own terminal and browser

Dated technical/research record; results and limitations apply to the versions described. Use [the README](../../README.md) for current status and planning.

Use `/Users/alpha/Ai village/AI Executive Team V2CHAT`. The default model is unchanged. The later experimental reasoning prototypes are not enabled.

1. If the app is running in your terminal, press **Control+C** there. Then run:

   ```sh
   cd "/Users/alpha/Ai village/AI Executive Team V2CHAT"
   ./company doctor
   ./company start
   ```

   Keep this terminal open. Use the browser address printed by the launcher and paste the key it copies. If ports are occupied, identify their owner before stopping anything. Do not delete data or recreate an existing `.env`. `init-local` is only for a genuinely fresh installation without configuration or company data.

2. Open **Decisions** → **Plan a first real-user test**. Enter:

   > Help me get the first real seller to test Reinstatly and give useful feedback.

3. Open **Add project facts or choose reviewed records**. Select only relevant records you have reviewed, if any. In **Project facts or corrections**, enter facts you can confirm. For the same development example, this short context uses your previously supplied product description and correction:

   > Reinstatly drafts a Plan of Action from a pasted Amazon suspension notice. The external CEO I spoke with never tested the tool and never replied afterward. Whether this is the seller-group founder is unknown. The last exchange date is unknown. No current eligible tester is confirmed. Previous outreach results and current access to seller groups are not confirmed in this brief.

   Correct anything that is no longer accurate. The application does not automatically know the history from this chat. A visible notice states whether saved project records were selected; manually entered facts are still included.

4. Click **Clarify my request**. Choose the actual intended-contact status, today's actual tool status, and your real available minutes. For the silent-contact example select **No reply after earlier contact**. Use **Yes, it works** only after today's check; otherwise skip. Click **Review brief with these answers**.

5. Read **Your next step** first. It should show one proposed step, why, what to do if blocked, estimated effort and the context used. It is explicitly application guidance. If you already confirmed the tool works, there should be no five-minute task merely to record that answer. With a silent contact, the plan must not infer lack of interest or automatically propose another follow-up.

6. Open the full checklist and full team-context sections only when you want the supporting detail. Verify that your full correction is retained. A known tool outage must pause invitations. Changed answers must invalidate the earlier confirmation.

7. If you want a new saved team result, click **Confirm brief and fill decision form**, review the filled form and choose **Start Decision** once. AI proposals remain unverified and may contain unsupported reasoning; the compact application panel is not proof that the executives reasoned correctly. Do not approve a direction, start preparation or execute actions just to test this page.

8. Refresh and check **Decision History**. New first-user results have the compact panel at the top. Open **AI proposals, objections and evidence — unverified** for the original model output. Older saved results retain their original content and show an unverified AI step rather than a newly invented application summary. If a connection fails, check request status/history before submitting again.

Please report: could you find the next step immediately; did the fallback make sense; and did the actual AI proposals use your facts correctly? Your earlier test already showed a saved result but failed clarity. Sprint 7 is closed with unfinished work carried forward; usefulness and dependency findings remain unresolved.
