/**
 * Executive Oversight & Reports API Client (US-24, US-25, S7-FE-1).
 *
 * Integrates with FastAPI Executive router:
 * - GET  /api/v1/executive/dashboard
 * - GET  /api/v1/executive/dashboard/departments/{id}
 * - POST /api/v1/executive/reports/generate
 * - GET  /api/v1/executive/reports
 * - GET  /api/v1/executive/reports/{id}
 * - GET  /api/v1/executive/reports/{id}/download
 */

import { apiClient } from "./client.js";
import { downloadAuthenticatedFile } from "./download.js";

/**
 * Fetch high-level organizational KPIs, project breakdown, task metrics, and department summaries.
 * Accessible to MNC_EXECUTIVE, ADMIN, and SYSTEM_ADMIN.
 * @returns {Promise<Object>} ExecutiveOverviewResponse
 */
export async function getExecutiveDashboard() {
  return apiClient.get("/api/v1/executive/dashboard");
}

/**
 * Fetch granular department projects, teams, and resource allocation.
 * Never call with null deptId (Unassigned).
 * @param {number|string} deptId
 * @returns {Promise<Object>} ExecutiveDepartmentDrilldownResponse
 */
export async function getDepartmentDrilldown(deptId) {
  if (deptId === null || deptId === undefined) {
    throw new Error("deptId is required for department drilldown");
  }
  return apiClient.get(`/api/v1/executive/dashboard/departments/${deptId}`);
}

/**
 * Generate a period-bounded executive management report (PDF or CSV).
 * @param {Object} payload
 * @param {string} payload.report_title
 * @param {string} payload.period_start YYYY-MM-DD
 * @param {string} payload.period_end YYYY-MM-DD
 * @param {"PDF"|"CSV"} [payload.format="PDF"]
 * @param {boolean} [payload.include_department_breakdown=false]
 * @returns {Promise<Object>} ExecutiveReportResponse
 */
export async function generateReport(payload) {
  return apiClient.post("/api/v1/executive/reports/generate", payload);
}

/**
 * List historical generated executive management reports (newest first).
 * @param {number} [page=1]
 * @param {number} [limit=20]
 * @returns {Promise<Object>} PaginatedExecutiveReportsResponse
 */
export async function listReports(page = 1, limit = 20) {
  return apiClient.get(`/api/v1/executive/reports?page=${page}&limit=${limit}`);
}

/**
 * Retrieve metadata for a single executive report.
 * @param {number|string} reportId
 * @returns {Promise<Object>} ExecutiveReportResponse
 */
export async function getReport(reportId) {
  return apiClient.get(`/api/v1/executive/reports/${reportId}`);
}

/**
 * Securely downloads an authenticated report file using Bearer token and triggers browser save.
 * @param {number|string} reportId
 * @param {string} [fallbackName="executive_report"]
 * @returns {Promise<{ blob: Blob, filename: string }>}
 */
export async function downloadReport(reportId, fallbackName = "executive_report") {
  const endpoint = `/api/v1/executive/reports/${reportId}/download`;
  return downloadAuthenticatedFile(endpoint, fallbackName);
}

export const executiveApi = {
  getExecutiveDashboard,
  getDepartmentDrilldown,
  generateReport,
  listReports,
  getReport,
  downloadReport,
};

export default executiveApi;
