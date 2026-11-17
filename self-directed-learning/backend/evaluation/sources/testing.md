# Testing: boundaries and interactions
Equivalence partitioning divides inputs into classes expected to be handled similarly. Testing representatives is a sampling strategy, not proof that all members behave identically. For a function accepting integers from 1 through 100 inclusive, below-range, valid-range and above-range are useful partitions. Values 0, 1, 2, 99, 100 and 101 probe the edges and their neighbors.

A unit test exercises a small unit in isolation, often replacing dependencies with controlled substitutes. An integration test checks interaction between components, such as an API and its database. Passing a unit test with a fake database does not establish that a real query or transaction works.

A useful test specifies input, expected outcome and the fault it could expose. More test cases alone do not imply better coverage. Test results provide evidence about the exercised behavior; they do not prove the absence of defects.
