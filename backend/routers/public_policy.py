"""Public policy resources required by Google Play.

These pages are intentionally served by the same production backend as the app
so Play Console and users can use stable HTTPS URLs outside the Android app.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["public-policy"])


_BASE_STYLE = """
:root{
  --bg:#F2FBF7;--surface:rgba(255,255,255,.86);--surface-strong:#FFFFFF;
  --text:#0A211A;--muted:#55736A;--brand:#0F8A6A;--brand-deep:#075E4A;
  --brand-soft:#DDF7EE;--accent:#F59E0B;--accent-soft:#FFF0D5;
  --border:#CFE4DC;--shadow:0 18px 60px rgba(7,94,74,.12);
}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:radial-gradient(circle at 12% 2%,rgba(25,185,138,.14),transparent 32%),radial-gradient(circle at 88% 10%,rgba(245,158,11,.10),transparent 30%),var(--bg);color:var(--text);line-height:1.65}
a{color:var(--brand-deep);font-weight:700;text-decoration-thickness:1px;text-underline-offset:3px}.shell{width:min(900px,100%);margin:0 auto;padding:20px 16px 48px}.topbar{display:flex;align-items:center;justify-content:space-between;gap:14px;padding:14px 16px;border:1px solid rgba(207,228,220,.9);background:rgba(255,255,255,.72);backdrop-filter:blur(18px);-webkit-backdrop-filter:blur(18px);border-radius:22px;box-shadow:0 8px 30px rgba(7,94,74,.07);position:sticky;top:10px;z-index:4}.brand{font-size:15px;font-weight:900;letter-spacing:.11em;color:var(--brand-deep)}.brand b{color:var(--accent)}.nav{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:7px}.nav a{text-decoration:none;font-size:12px;padding:8px 10px;border-radius:999px;background:var(--brand-soft);color:var(--brand-deep)}.hero{margin:22px 0 16px;padding:30px 26px;border-radius:28px;background:linear-gradient(145deg,rgba(255,255,255,.94),rgba(255,255,255,.74));border:1px solid rgba(207,228,220,.95);box-shadow:var(--shadow);overflow:hidden;position:relative}.hero:after{content:"";position:absolute;right:-75px;top:-95px;width:230px;height:230px;border-radius:50%;background:linear-gradient(145deg,rgba(25,185,138,.16),rgba(245,158,11,.12));filter:blur(2px)}.kicker{display:inline-flex;align-items:center;gap:7px;padding:7px 11px;border-radius:999px;background:var(--accent-soft);color:#8A5100;font-size:12px;font-weight:800;letter-spacing:.04em;text-transform:uppercase}.hero h1{position:relative;z-index:1;margin:14px 0 7px;font-size:clamp(29px,6vw,48px);line-height:1.06;letter-spacing:-.035em}.hero p{position:relative;z-index:1;margin:0;color:var(--muted);max-width:690px}.updated{display:block;margin-top:14px;font-size:12px;color:var(--muted)}.grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.card{padding:21px;border-radius:22px;background:var(--surface);border:1px solid var(--border);box-shadow:0 9px 28px rgba(7,94,74,.06);backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px)}.card.wide{grid-column:1/-1}.card h2{font-size:18px;margin:0 0 8px;color:var(--brand-deep)}.card p{margin:0;color:#294B41}.card p+p{margin-top:10px}.footer{margin-top:18px;padding:20px;text-align:center;color:var(--muted);font-size:12px}.footer strong{color:var(--brand-deep)}.form-card{max-width:680px;margin:0 auto;padding:24px;border-radius:24px;background:var(--surface);border:1px solid var(--border);box-shadow:var(--shadow)}label{display:block;font-size:13px;font-weight:800;color:var(--brand-deep);margin-top:16px}input,textarea,button{width:100%;font:inherit;border-radius:14px;padding:13px 14px;margin-top:7px}input,textarea{color:var(--text);background:rgba(255,255,255,.88);border:1px solid var(--border);outline:none}input:focus,textarea:focus{border-color:var(--brand);box-shadow:0 0 0 3px rgba(15,138,106,.12)}button{border:0;background:linear-gradient(135deg,var(--brand),var(--brand-deep));color:#fff;font-weight:850;cursor:pointer;box-shadow:0 10px 24px rgba(15,138,106,.18)}button.secondary{background:var(--brand-soft);color:var(--brand-deep);box-shadow:none}.notice{margin-top:15px;padding:12px 14px;border-radius:14px;background:var(--accent-soft);color:#704100;font-size:13px}.muted{color:var(--muted);font-size:13px}#codeStep{display:none}#status{margin-top:16px;white-space:pre-wrap;font-weight:700;color:var(--brand-deep)}
@media(max-width:680px){.shell{padding:12px 12px 36px}.topbar{top:6px;border-radius:18px}.brand{font-size:13px}.nav a{font-size:11px;padding:7px 9px}.hero{padding:24px 18px;border-radius:24px}.grid{grid-template-columns:1fr}.card.wide{grid-column:auto}.card{padding:18px;border-radius:19px}}
"""


def _page(title: str, kicker: str, intro: str, content: str) -> str:
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#0F8A6A"><title>{title}</title><style>{_BASE_STYLE}</style></head>
<body><main class="shell">
<header class="topbar"><div class="brand">TRACK MY <b>RMC</b></div><nav class="nav"><a href="/privacy_policy">Privacy</a><a href="/terms">Terms</a><a href="/account-deletion">Delete Account</a></nav></header>
<section class="hero"><span class="kicker">{kicker}</span><h1>{title}</h1><p>{intro}</p><small class="updated">Last updated: 27 August 2026</small></section>
{content}
<footer class="footer">TrackMyRMC / Concrete King · Powered by <strong>GOLD-e Tech</strong><br>Support: <a href="mailto:support@goldetech.com">support@goldetech.com</a></footer>
</main></body></html>"""


_PRIVACY_CONTENT = """
<section class="grid">
<article class="card"><h2>Who operates this service</h2><p>TrackMyRMC / Concrete King is operated by GOLD-e Tech. Privacy and account-deletion questions can be sent to <a href="mailto:support@goldetech.com">support@goldetech.com</a>.</p></article>
<article class="card"><h2>Account & operational information</h2><p>We use mobile number or email for authentication, and profile, role, plant assignment and KYC status for access control. Operational records may include RMC orders, sites, dispatches, delivery trips, challans, proof of delivery, signatures, invoices, payments, attendance, incidents and support records when those features are used.</p></article>
<article class="card"><h2>Location</h2><p>Foreground location may be used for attendance, nearby-plant or delivery operations when initiated by the user. For an assigned Driver delivery only, TrackMyRMC may collect precise background location to enable live mixer delivery tracking when the app is closed or not in use. Tracking stops when the delivery is completed. Location is not used for advertising.</p></article>
<article class="card"><h2>Camera, photos & files</h2><p>Camera access is requested only when a Driver chooses to capture a proof-of-delivery site photo. On supported Android versions, existing photos are selected through the system photo picker without broad photo or storage access. KYC consent flows may use approved verification providers such as DigiLocker where enabled.</p></article>
<article class="card"><h2>Notifications</h2><p>If a user enables notifications, TrackMyRMC registers a device push token to deliver account-relevant alerts such as order approvals, dispatch and delivery updates, assigned trips, KYC decisions and safety alerts. Notification permission is optional.</p></article>
<article class="card"><h2>Sharing & service providers</h2><p>Data is shared only as needed for the service and according to role permissions. Infrastructure, mapping, notification, payment, KYC and authentication providers may process the minimum data needed for enabled features. TrackMyRMC does not sell personal data and does not use location for advertising.</p></article>
<article class="card wide"><h2>Retention & deletion</h2><p>Users can request account deletion from inside TrackMyRMC or from the public <a href="/account-deletion">Delete Account page</a>. After verified deletion is completed, sign-in identifiers, profile data, sessions, saved customer sites, app notifications and registered push tokens are removed or anonymized. Certain statutory transaction records may be retained only where required for legal, tax, fraud-prevention or accounting obligations.</p></article>
<article class="card wide"><h2>Security & user choices</h2><p>TrackMyRMC uses authenticated sessions and role-based access controls. Sensitive Android permissions are requested only in the feature that needs them. Users may decline optional permissions or revoke them in Android settings.</p></article>
</section>
"""


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
@router.get("/privacy_policy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy_page():
    return _page(
        "Privacy Policy",
        "Your data, clearly explained",
        "How TrackMyRMC collects, uses, protects and deletes information across ordering, plant operations and delivery tracking.",
        _PRIVACY_CONTENT,
    )


_TERMS_CONTENT = """
<section class="grid">
<article class="card"><h2>Using TrackMyRMC</h2><p>TrackMyRMC provides digital tools for ready-mix concrete discovery, ordering, plant operations, dispatch, delivery tracking, challans, KYC, payments and related workflows. Features available to you depend on your account role and plant configuration.</p></article>
<article class="card"><h2>Accounts & access</h2><p>You are responsible for using accurate account information and keeping access to your phone, email and authenticated session secure. Role-based permissions must not be bypassed or shared with unauthorized users.</p></article>
<article class="card"><h2>Orders & commercial terms</h2><p>Order quantities, concrete grades, delivery schedules, rates, taxes, payment terms and acceptance remain subject to the commercial terms confirmed between the customer and the selected plant. App status information supports the transaction but does not replace the parties' agreed commercial documents.</p></article>
<article class="card"><h2>Location & delivery operations</h2><p>Driver and delivery features may use location while an assigned trip is active. Users must use tracking, proof-of-delivery and attendance features only for legitimate operational purposes and in accordance with applicable workplace and privacy requirements.</p></article>
<article class="card"><h2>Payments & third parties</h2><p>Where payment, mapping, KYC, notification or authentication services are enabled, those services may also be subject to the provider's terms. TrackMyRMC does not control third-party service availability.</p></article>
<article class="card"><h2>Acceptable use</h2><p>Do not misuse the service, attempt unauthorized access, submit fraudulent records, interfere with tracking or security controls, or use TrackMyRMC for unlawful activity.</p></article>
<article class="card wide"><h2>Service availability & changes</h2><p>We may update features, security controls and these terms as the service evolves. Reasonable efforts are made to keep the service available, but uninterrupted operation cannot be guaranteed where networks, devices, third-party services or maintenance are outside our control.</p></article>
<article class="card wide"><h2>Contact</h2><p>Questions about these terms can be sent to <a href="mailto:support@goldetech.com">support@goldetech.com</a>. For privacy information, see the <a href="/privacy_policy">Privacy Policy</a>.</p></article>
</section>
"""


@router.get("/terms", response_class=HTMLResponse, include_in_schema=False)
async def terms_page():
    return _page(
        "Terms & Conditions",
        "TrackMyRMC service terms",
        "These terms describe the basic rules for using TrackMyRMC and its ready-mix concrete operational services.",
        _TERMS_CONTENT,
    )


_DELETE_FORM = """
<section class="form-card">
<h2 style="margin:0;color:var(--brand-deep)">Verify your account</h2>
<p class="muted">Request account deletion without signing in. We verify ownership with a one-time code sent to your registered mobile number or email.</p>
<div class="notice">After verified deletion is completed, sign-in identity, profile data and active sessions are removed or anonymized. Statutory transaction records may be retained only where legally required.</div>
<div id="identifyStep"><label for="identifier">Registered mobile number or email</label><input id="identifier" autocomplete="username" placeholder="Mobile number or email"><button id="send">Send verification code</button></div>
<div id="codeStep"><label for="code">Verification code</label><input id="code" inputmode="numeric" maxlength="8" placeholder="Enter OTP"><label for="reason">Reason (optional)</label><textarea id="reason" rows="3" placeholder="Tell us why you are deleting your account"></textarea><label for="confirm">Type DELETE to confirm</label><input id="confirm" autocomplete="off" placeholder="DELETE"><button id="submit">Request account deletion</button><button class="secondary" id="change">Change mobile/email</button></div>
<div id="status" role="status" aria-live="polite"></div>
</section>
<script>
const $=id=>document.getElementById(id); const status=$('status');
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let j={};try{j=await r.json()}catch{}if(!r.ok)throw new Error(j.detail||'Request failed');return j}
$('send').onclick=async()=>{status.textContent='';const identifier=$('identifier').value.trim();if(identifier.length<3){status.textContent='Enter your registered mobile number or email.';return}try{const r=await post('/api/auth/request-otp',{identifier});$('identifyStep').style.display='none';$('codeStep').style.display='block';status.textContent='Verification code sent via '+(r.channel==='email'?'email':'SMS')+'.'}catch(e){status.textContent=e.message}};
$('change').onclick=()=>{$('codeStep').style.display='none';$('identifyStep').style.display='block';status.textContent=''};
$('submit').onclick=async()=>{status.textContent='';if($('confirm').value.trim().toUpperCase()!=='DELETE'){status.textContent='Type DELETE to confirm.';return}try{await post('/api/account-deletion/public-request',{identifier:$('identifier').value.trim(),code:$('code').value.trim(),confirm:'DELETE',reason:$('reason').value.trim()||null});$('codeStep').style.display='none';status.textContent='Deletion request submitted. Your request has been recorded for completion.'}catch(e){status.textContent=e.message}};
</script>
"""


@router.get("/delete-account", response_class=HTMLResponse, include_in_schema=False)
@router.get("/account-deletion", response_class=HTMLResponse, include_in_schema=False)
async def delete_account_page():
    return _page(
        "Delete Account",
        "Account control",
        "Delete your TrackMyRMC account through a verified, self-service request.",
        _DELETE_FORM,
    )
