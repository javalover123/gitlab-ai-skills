---
name: incident-follow-up
description: Create a follow-up in incident.io linked to a GitLab work item.
---

# Incident Follow-Up Issue Skill

When asked to create a follow-up issue for an incident (e.g. "create a follow-up issue per <MR note URL> linked to <INC-XXXX>"), perform the following steps:

## Steps

1. **Fetch the MR note** using `glab api` to read the note content and understand what follow-up is being requested.

   ```bash
   glab api "projects/<url-encoded-project-path>/merge_requests/<id>/notes/<note_id>"
   ```

2. **Fetch the MR details** using the `mcp__gitlab-com__get_merge_request` tool to get the title, description, labels, and context.

3. **Fetch the incident details** using the `mcp__incident-io__incident_show` tool to get the incident summary, severity, affected services, and permalink.

4. **Create the GitLab follow-up issue** using `mcp__gitlab-com__create_issue` in the same project as the MR. The issue should include:
   - A clear title describing the follow-up action (e.g. "Revert temporary X → Y redirect once Z is resolved")
   - A description with:
     - **Summary** of why the temporary change was made
     - **Follow-up actions** as a checklist
     - **References** linking back to the incident (incident.io permalink) and the MR
   - The same labels as the MR

5. **Create an incident.io follow-up** using `mcp__incident-io__follow_up_create` on the incident, with:
   - A title matching the GitLab issue
   - A description linking to the newly created GitLab issue

6. **Add a note to the MR** using `glab api` referencing the new issue and the incident:

   ```bash
   glab api "projects/<url-encoded-project-path>/merge_requests/<id>/notes" \
     --method POST \
     --field "body=Created follow-up issue #<work_item_id> to track <action> (linked to [INC-XXXX](<incident permalink>))."
   ```

## Required MCP servers

- `gitlab-com` — for reading MR details and creating the GitLab issue
- `incident-io` — for reading incident details and creating the incident.io follow-up
