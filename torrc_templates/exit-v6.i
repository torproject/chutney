# Must be included after relay-non-exit.tmpl
ExitRelay 1

# 1. Allow exiting to IPv6 localhost and private networks by default
# ------------------------------------------------------------------
IPv6Exit 1

# Each IPv6 tor instance is configured with Address [::1] by default
# This currently only applies to bridges
ExitPolicy accept6 [::1]:*

# If you only want tor to connect to localhost, disable these lines:
# This may cause network failures in some circumstances
ExitPolicyRejectPrivate 0
ExitPolicy accept6 private:*

# 2. Optionally: Accept all IPv6 addresses, that is, the public internet
# ----------------------------------------------------------------------
# ExitPolicy accept6 *:*

# 3. Finally, reject all IPv6 addresses which haven't been permitted
# ------------------------------------------------------------------
ExitPolicy reject6 *:*
