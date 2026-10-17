import { apiRequest } from './authService'

export const dashboardService = {
  companyOverview: () => apiRequest('/api/v1/dashboard/company-overview'),
}
