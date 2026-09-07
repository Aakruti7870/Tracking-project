# Google Play location review checklist

Use the isolated **REVIEW APP** access from the sign-in screen.

## Customer / Nearby Plants

1. Choose **User / Customer** in Google Play Review Access and sign in with the reusable reviewer OTP supplied in Play Console.
2. Open **Nearby Plants**.
3. TrackMyRMC first shows an in-app explanation stating that precise location is used only while the app is open to rank nearby RMC plants.
4. Choose **Use my location** to continue to Android's foreground-location permission prompt, or choose **Not now** to verify that registered plants remain browsable.
5. The seeded **TrackMyRMC Play Review Plant** remains available for inspection even when location is declined.

## Driver / Background Location

1. Choose **Driver** in Google Play Review Access and sign in.
2. On Driver Home, open **Current Trip PLAY-REVIEW-001**.
3. TrackMyRMC shows the prominent active-delivery location disclosure before Android requests location permission.
4. Choose **Agree & Continue**.
5. Continue through Android's foreground permission prompt. Background location is requested only for the active delivery, after the app-owned background disclosure.
6. Choosing **Not now** keeps the trip workflow available without background location sharing.

## Other permission surfaces

- Notification permission is preceded by TrackMyRMC's notification explanation and remains optional.
- POD camera access is requested only when the reviewer chooses to capture a site photo.
- Android gallery selection uses the system picker and does not request broad media/storage permission.

This checklist is reviewer guidance only. It does not expose or change production credentials, authentication boundaries, or platform-admin access.
