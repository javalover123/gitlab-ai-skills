// Settings > GitLab Credits (ee/app/assets/javascripts/pages/groups/settings/gitlab_credits_dashboard/index.js):
// GitLab's real initGitlabCreditsDashboard, answered by the in-browser mocks.
import '@demo/src/shell/boot';
import { initGitlabCreditsDashboard } from 'ee/usage_quotas/wallet_agnostic_credits_dashboard/index';
import './mocks';

initGitlabCreditsDashboard(document.getElementById('js-group-usage-billing-dashboard'));
