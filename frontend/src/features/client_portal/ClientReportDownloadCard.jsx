import React, { useState } from "react";
import { exportClientReportPdf } from "../../api/clientPortalApi";
import { useToast } from "../../components/common/Toast";

/**
 * ClientReportDownloadCard Component (US-41)
 *
 * Dedicated executive download card for authenticated project progress reports in PDF format.
 */
export default function ClientReportDownloadCard({ projectId, projectCode, projectName }) {
  const toast = useToast();
  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async () => {
    if (!projectId) return;
    setIsExporting(true);
    try {
      const result = await exportClientReportPdf(projectId);
      toast.success(
        `Report downloaded successfully: ${result?.filename || `Project_Report_${projectId}.pdf`}`
      );
    } catch (err) {
      const msg =
        err?.response?.data?.detail ||
        err?.message ||
        "Failed to generate and download progress report PDF.";
      toast.error(msg);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="client-card" data-testid="client-report-download-card">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", flexWrap: "wrap", gap: "20px" }}>
        <div style={{ maxWidth: "600px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" }}>
            <span style={{ fontSize: "20px" }}>📄</span>
            <h3 className="client-card-title" style={{ margin: 0 }}>
              Executive Progress Report (PDF)
            </h3>
          </div>
          <p className="client-page-subtitle" style={{ lineHeight: "1.6" }}>
            Generate and download a comprehensive, audit-ready PDF summary for{" "}
            <strong>{projectName || projectCode || `Project #${projectId}`}</strong>. Includes milestone delivery
            timelines, completion velocity metrics, and full deliverable signoff audit logs.
          </p>

          <div style={{ marginTop: "14px", display: "flex", gap: "16px", fontSize: "12px", color: "#64748b" }}>
            <span>🔒 Authenticated Client Access</span>
            <span>•</span>
            <span>✓ Audit-compliant</span>
            <span>•</span>
            <span>⚡ Real-time snapshot</span>
          </div>
        </div>

        <div>
          <button
            type="button"
            className="btn-primary"
            onClick={handleExport}
            disabled={isExporting}
            data-testid="export-pdf-report-btn"
            style={{ padding: "10px 18px", fontSize: "14px" }}
          >
            {isExporting ? "Generating PDF..." : "📥 Export Progress Report (PDF)"}
          </button>
        </div>
      </div>
    </div>
  );
}
