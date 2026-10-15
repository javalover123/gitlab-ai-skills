// Settings > GitLab Credits > Credit caps
// (ee/app/assets/javascripts/pages/groups/settings/gitlab_credits_dashboard/credit_caps/index.js), unmodified init.
import '@demo/src/shell/boot';
import { initCreditCapsDashboard } from 'ee/usage_quotas/wallet_agnostic_credits_dashboard/credit_caps/index';
import './mocks';

initCreditCapsDashboard(document.getElementById('js-group-credit-caps-dashboard'));
