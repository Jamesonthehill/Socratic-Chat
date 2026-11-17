# Defensive account-system design
Authentication verifies a claimed identity. Authorization decides whether that identity may perform a particular action on a particular resource. Being logged in does not grant permission to read every account. Permission checks belong on the server for each protected operation; hiding a button in a browser is not enforcement.

Least privilege grants only the access needed for the assigned function. A support agent who needs to view ticket summaries does not automatically need access to payment details or administrator actions. Deny by default when no permission is established, and check ownership or other policy-relevant relationships rather than trusting a client-supplied account identifier.

Parameterized database queries keep query structure separate from supplied values. String concatenation of untrusted input into SQL can change query meaning. Parameterization does not replace authorization and does not by itself make dynamically constructed table names safe. Use only hypothetical systems in these exercises; do not request credentials, exploit real services or perform network attacks.
