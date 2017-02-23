# Must be included after relay-non-exit.tmpl
ExitRelay 1

# 1. Allow exiting to IPv4 localhost and private networks by default
# -------------------------------------------------------------

# Each IPv4 tor instance is configured with Address 127.0.0.1 by default
ExitPolicy accept 127.0.0.0/8:*

# If you only want tor to connect to localhost, disable these lines:
# This may cause network failures in some circumstances
ExitPolicyRejectPrivate 0
ExitPolicy accept private:*

# 2. Optionally: Allow exiting to the entire IPv4 internet on HTTP(S)
# -------------------------------------------------------------------

# 2. or 3. are required to work around #11264 with microdescriptors enabled
# "The core of this issue appears to be that the Exit flag code is
#  optimistic (just needs a /8 and 2 ports), but the microdescriptor
#  exit policy summary code is pessimistic (needs the entire internet)."
# An alternative is to disable microdescriptors and use regular
# descriptors, as they do not suffer from this issue.
#ExitPolicy accept *:80
#ExitPolicy accept *:443

# 3. Optionally: Accept all IPv4 addresses, that is, the public internet
# ----------------------------------------------------------------------
ExitPolicy accept *:*

# 4. Finally, reject all IPv4 addresses which haven't been permitted
# ------------------------------------------------------------------
ExitPolicy reject *:*
