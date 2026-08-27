"""Public policy resources required by Google Play.

These pages are intentionally served by the same production backend as the app
so Play Console can use stable HTTPS URLs that remain available outside the
Android app.
"""
from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["public-policy"])


@router.get("/privacy", response_class=HTMLResponse, include_in_schema=False)
async def privacy_policy_page():
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>TrackMyRMC Privacy Policy</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;max-width:820px;margin:0 auto;padding:32px 20px;line-height:1.6;color:#17211f}h1,h2{color:#071b17}section{margin:28px 0}small{color:#64706d}a{color:#08765f}</style></head>
<body><h1>TrackMyRMC Privacy Policy</h1><small>Last updated: 27 August 2026</small>
<section><h2>Who operates this service</h2><p>TrackMyRMC / Concrete King is operated by GOLD-e Tech. Privacy and account-deletion questions can be sent to <a href="mailto:support@goldetech.com">support@goldetech.com</a>.</p></section>
<section><h2>Account and operational information</h2><p>We use mobile number or email for authentication, and profile, role, plant assignment and KYC status for access control. Operational records may include ready-mix concrete orders, sites, dispatches, delivery trips, challans, proof of delivery, signatures, invoices, payments, attendance, incidents and support records when those features are used.</p></section>
<section><h2>Location</h2><p>Foreground location may be used for location-aware features such as attendance, nearby-plant or delivery operations when initiated by the user. For an assigned Driver delivery only, TrackMyRMC may collect precise location in the background to enable live mixer delivery tracking even when the app is closed or not in use. During that active trip, location is sent to TrackMyRMC and may be shown to the assigned plant and the authorized customer tracking view. Background tracking stops when the delivery is completed. Location is not used for advertising.</p></section>
<section><h2>Camera, photos and files</h2><p>Camera access is requested only when a Driver chooses to capture a proof-of-delivery site photo. On supported Android versions, existing photos are selected through the system photo picker without broad photo or storage access. KYC document and consent flows use approved verification providers such as DigiLocker where enabled.</p></section>
<section><h2>Notifications</h2><p>If a user chooses to enable notifications, TrackMyRMC registers a device push token to deliver account-relevant alerts such as order approvals, dispatch and delivery updates, assigned trips, KYC decisions and safety alerts. Notification permission is optional.</p></section>
<section><h2>Sharing and service providers</h2><p>Data is shared only as needed for the service and according to role permissions. Infrastructure, mapping, notification, payment, KYC and authentication providers may process the minimum data needed for their enabled features. TrackMyRMC does not sell personal data and does not use location for advertising.</p></section>
<section><h2>Retention and deletion</h2><p>Users can request account deletion from inside TrackMyRMC or from the public <a href="/delete-account">Delete Account page</a>. After verified deletion is completed, sign-in identifiers, profile data, sessions, saved customer sites, app notifications and registered push tokens are removed or anonymized. Certain statutory transaction records may be retained only where required for legal, tax, fraud-prevention or accounting obligations.</p></section>
<section><h2>Security and user choices</h2><p>TrackMyRMC uses authenticated sessions and role-based access controls. Sensitive Android permissions are requested in the feature that needs them. Users may decline optional permissions or revoke them in Android settings.</p></section>
</body></html>"""


@router.get("/delete-account", response_class=HTMLResponse, include_in_schema=False)
async def delete_account_page():
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Delete TrackMyRMC Account</title>
<style>body{font-family:system-ui,-apple-system,sans-serif;max-width:640px;margin:0 auto;padding:32px 20px;color:#17211f;background:#f7faf9}main{background:white;border:1px solid #dfe8e5;border-radius:18px;padding:24px}label{display:block;font-weight:600;margin-top:16px}input,textarea,button{box-sizing:border-box;width:100%;font:inherit;padding:12px;border-radius:10px;border:1px solid #bccac6;margin-top:6px}button{background:#08765f;color:white;border:0;font-weight:700;margin-top:18px;cursor:pointer}.secondary{background:#eef5f2;color:#164b40}#codeStep{display:none}#status{margin-top:16px;white-space:pre-wrap}.muted{color:#64706d;font-size:.92rem}</style></head>
<body><main><h1>Delete TrackMyRMC Account</h1><p>This public page lets you request account deletion without signing in. We verify ownership with a one-time code sent to your registered mobile number or email.</p>
<p class="muted">When deletion is completed, sign-in identity, profile data and active sessions are removed or anonymized. Statutory transaction records may be retained only where legally required.</p>
<div id="identifyStep"><label for="identifier">Registered mobile number or email</label><input id="identifier" autocomplete="username"><button id="send">Send verification code</button></div>
<div id="codeStep"><label for="code">Verification code</label><input id="code" inputmode="numeric" maxlength="8"><label for="reason">Reason (optional)</label><textarea id="reason" rows="3"></textarea><label for="confirm">Type DELETE to confirm</label><input id="confirm" autocomplete="off"><button id="submit">Request account deletion</button><button class="secondary" id="change">Change mobile/email</button></div>
<div id="status" role="status" aria-live="polite"></div><p class="muted">Privacy policy: <a href="/privacy">TrackMyRMC Privacy Policy</a> · Support: <a href="mailto:support@goldetech.com">support@goldetech.com</a></p></main>
<script>
const $=id=>document.getElementById(id); const status=$('status');
async function post(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});let j={};try{j=await r.json()}catch{}if(!r.ok)throw new Error(j.detail||'Request failed');return j}
$('send').onclick=async()=>{status.textContent='';const identifier=$('identifier').value.trim();if(identifier.length<3){status.textContent='Enter your registered mobile number or email.';return}try{const r=await post('/api/auth/request-otp',{identifier});$('identifyStep').style.display='none';$('codeStep').style.display='block';status.textContent='Verification code sent via '+(r.channel==='email'?'email':'SMS')+'.'}catch(e){status.textContent=e.message}};
$('change').onclick=()=>{$('codeStep').style.display='none';$('identifyStep').style.display='block';status.textContent=''};
$('submit').onclick=async()=>{status.textContent='';if($('confirm').value.trim().toUpperCase()!=='DELETE'){status.textContent='Type DELETE to confirm.';return}try{await post('/api/account-deletion/public-request',{identifier:$('identifier').value.trim(),code:$('code').value.trim(),confirm:'DELETE',reason:$('reason').value.trim()||null});$('codeStep').style.display='none';status.textContent='Deletion request submitted. Your request has been recorded for completion.'}catch(e){status.textContent=e.message}};
</script></body></html>"""
