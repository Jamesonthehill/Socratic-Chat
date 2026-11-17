# Git: local snapshots and collaboration
The working tree contains editable files. The index, also called the staging area, records the content prepared for the next commit. A commit records the staged snapshot, not every current working-tree change. Editing a file after staging it does not automatically stage those later edits. A branch name points to a commit; commits record parent relationships.

Fetching downloads objects and updates remote-tracking references; it does not itself merge remote changes into the current branch or modify the working tree. Pull first fetches and then integrates changes, using a strategy determined by configuration or command options. It is therefore unsafe to treat fetch and pull as identical operations.

A merge may stop for conflicting edits. Inspect the conflict, decide the intended combined content, edit and test the result, stage the resolved files, and finish the merge. Choosing one side blindly can discard valid work. A merge conflict is not proof that the repository is corrupted.
