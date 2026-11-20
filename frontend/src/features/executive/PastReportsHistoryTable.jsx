import React, { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listReports, downloadReport } from "../../api/executiveApi.js";
import { useToast } from "../../components/common/Toast.jsx";
import { formatBytes } from "./executiveUtils.js";

/**
 * PastReportsHistoryTable
 * Displays paginated history of executive reports with authenticated file download actions.
 *
 * @param {Object} props
 * @param {any} props.refreshTrigger Trigger value that forces query refetch when updated
 */
export default function PastReportsHistoryTable({ refreshTrigger }) {
  const toast = useToast();
  const [page, setPage] = useState(1);
  const limit = 10;
  const [downloadingId, setDownloadingId] = useState(null);

  const { data, isLoading, error, isPlaceholderData } = useQuery({
    queryKey: ["executive", "reports", page, limit, refreshTrigger],
    queryFn: () => listReports(page, limit),
    staleTime: 60 * 1000,
  });

  const reports = data?.items || [];
  const total = data?.total || 0;
  const totalPages = Math.ceil(total / limit) || 1;

  const handleDownload = async (report) => {
    setDownloadingId(report.report_id);
    try {
      const ext = report.format?.toLowerCase() || "pdf";
      const fallback = `${report.report_title || "executive_report"}.${ext}`;
      await downloadReport(report.report_id, fallback);
      toast.success(`Download started: ${fallback}`);
    } catch (err) {
      toast.error(err.message || "Failed to download report file.");
    } finally {
      setDownloadingId(null);
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return "-";
    try {
      return new Date(isoString).toLocaleString(undefined, {
        year: "numeric",
        month: "short",
        day: "numeric",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch {
      return isoString;
    }
  };

  return (
    <div className="exec-table-card" aria-label="Executive Management Report History">
      <div className="exec-card-header">
        <div>
          <h3 className="exec-card-title">Management Report Archive</h3>
          <p className="exec-card-subtitle">
            Historical executive briefs and period audits ({total} total)
          </p>
        </div>
      </div>

      {isLoading && (
        <div className="exec-drilldown-loading">
          <div className="exec-spinner" aria-hidden="true" />
          <p>Loading report archive...</p>
        </div>
      )}

      {error && (
        <div className="exec-drilldown-error">
          <p className="exec-error-text">
            ⚠️ Failed to load report archive: {error.message || "Unknown error"}
          </p>
        </div>
      )}

      {!isLoading && !error && reports.length === 0 && (
        <div className="exec-empty-state">
          <p className="exec-empty-text">No management reports have been generated yet.</p>
          <p className="exec-empty-subtext">
            Use the form above to generate your first period-bounded executive report.
          </p>
        </div>
      )}

      {!isLoading && !error && reports.length > 0 && (
        <>
          <div className="exec-table-responsive">
            <table className="exec-main-table">
              <thead>
                <tr>
                  <th>Title</th>
                  <th>Format</th>
                  <th>Reporting Period</th>
                  <th>Generated At</th>
                  <th>File Size</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {reports.map((report) => {
                  const isDownloadingThis = downloadingId === report.report_id;
                  const formatUpper = (report.format || "PDF").toUpperCase();

                  return (
                    <tr key={report.report_id}>
                      <td className="exec-font-semibold">{report.report_title}</td>
                      <td>
                        <span className={`exec-format-badge format-${formatUpper.toLowerCase()}`}>
                          {formatUpper}
                        </span>
                      </td>
                      <td>
                        {report.period_start} to {report.period_end}
                      </td>
                      <td>{formatDate(report.generated_at)}</td>
                      <td>{formatBytes(report.file_size_bytes)}</td>
                      <td>
                        <button
                          type="button"
                          className="exec-download-action-btn"
                          onClick={() => handleDownload(report)}
                          disabled={isDownloadingThis}
                          aria-label={`Download ${report.report_title}`}
                        >
                          {isDownloadingThis ? "Downloading..." : "⬇ Download"}
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination Controls */}
          <div className="exec-pagination">
            <div className="exec-pagination-info">
              Showing {(page - 1) * limit + 1}–{Math.min(page * limit, total)} of {total} reports
            </div>
            <div className="exec-pagination-buttons">
              <button
                type="button"
                className="exec-page-btn"
                onClick={() => setPage((p) => Math.max(1, p - 1))}
                disabled={page <= 1}
              >
                Previous
              </button>
              <span className="exec-page-counter">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                className="exec-page-btn"
                onClick={() => {
                  if (!isPlaceholderData && page < totalPages) {
                    setPage((p) => p + 1);
                  }
                }}
                disabled={page >= totalPages || isPlaceholderData}
              >
                Next
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
