export function VerificationNotice() {
  return (
    <p className="notice" role="status">
      Verified email is required for bookings and hosting. Email delivery is not
      configured in this demo, so no verification email has been sent. For local
      testing, use the synthetic verified demo accounts described in the README.
    </p>
  );
}
