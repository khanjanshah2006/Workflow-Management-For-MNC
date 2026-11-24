import { apiClient } from "./client.js";
import { downloadAuthenticatedFile } from "./download.js";

/**
 * Client Portal API Service (US-20, US-21, US-22, US-41)
 * Provides methods for client-scoped project summaries, milestones,
 * deliverables, signoff feedback, and authenticated PDF report downloads.
 */

/**
 * List contracted projects with milestone progress (US-20).
 * @returns {Promise<Array<Object>>}
 */
export async function getClientProjects() {
  return apiClient.get("/api/v1/client/projects");
}

/**
 * View delivery milestones for a contracted project (US-21).
 * @param {number|string} projectId
 * @returns {Promise<Array<Object>>}
 */
export async function getClientMilestones(projectId) {
  return apiClient.get(`/api/v1/client/projects/${projectId}/milestones`);
}

/**
 * List published client deliverables for a project (US-22).
 * @param {number|string} projectId
 * @returns {Promise<Array<Object>>}
 */
export async function getClientDeliverables(projectId) {
  return apiClient.get(`/api/v1/client/projects/${projectId}/deliverables`);
}

/**
 * Submit feedback or formal signoff on a deliverable (US-22).
 * @param {number|string} deliverableId
 * @param {{ decision: 'ACCEPTED'|'CHANGES_REQUESTED', rating: number, comments?: string }} payload
 * @returns {Promise<Object>}
 */
export async function submitDeliverableFeedback(deliverableId, { decision, rating, comments }) {
  return apiClient.post(`/api/v1/client/deliverables/${deliverableId}/feedback`, {
    decision,
    rating,
    comments: comments ? comments.trim() : null,
  });
}

/**
 * Download authenticated progress report PDF (US-41).
 * @param {number|string} projectId
 * @returns {Promise<{ blob: Blob, filename: string }>}
 */
export async function exportClientReportPdf(projectId) {
  return downloadAuthenticatedFile(
    `/api/v1/client/projects/${projectId}/report/export`,
    `Project_Report_${projectId}.pdf`
  );
}

export const clientPortalApi = {
  getClientProjects,
  getClientMilestones,
  getClientDeliverables,
  submitDeliverableFeedback,
  exportClientReportPdf,
};
