# A client that only uses IPv6 ORPorts
${include:client-only-v6-md.i}

# Due to Tor bug #19608, microdescriptors can't be used by IPv6-only clients
# running tor 0.2.9 and earlier
UseMicrodescriptors 0
