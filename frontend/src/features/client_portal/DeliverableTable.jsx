import React, { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { getClientDeliverables } from "../../api/clientPortalApi";
import { deliverableStatusTone, formatDate } from "./clientPortalUtils";
import SignoffModal from "./SignoffModal";

/**
 * DeliverableTable Component (US-22)
 *
 * Client deliverable review table displaying submitted assets, versions,
 * previous feedback ratings, and providing the "Review & Sign off" action modal.
 */
export default function DeliverableTable({ projectId }) {
  const queryClient = useQueryClient();
  const [selectedDeliverable, setSelectedDeliverable] = useState(null);

  const {
    data: deliverables = [],
    isLoading,
    isError,
    error,
    refetch,
  } = useQuery({
    queryKey: ["clientDeliverables", projectId],
    queryFn: () => getClientDeliverables(projectId),
    enabled: Boolean(projectId),
  });

  const handleSignoffSuccess = () => {
    queryClient.invalidateQueries({ queryKey: ["clientDeliverables", projectId] });
    queryClient.invalidateQueries({ queryKey: ["clientProjects"] });
  };

  if (isLoading) {
    return (
      <div className="client-loading-spinner" role="status">
        <div className="placeholder-symbol">⏳</div>
        <p>Loading project deliverables...</p>
      </div>
    );
  }

  if (isError) {
    return (
      <div className="client-empty-state" style={{ borderColor: "#fca5a5" }}>
        <div style={{ fontSize: "2rem", marginBottom: "8px" }}>⚠️</div>
        <h3>Failed to load deliverables</h3>
        <p>{error?.message || "Could not retrieve deliverables list."}</p>
        <button
          type="button"
          className="btn-secondary"
          onClick={() => refetch()}
          style={{ marginTop: "12px" }}
        >
          Retry
        </button>
      </div>
    );
  }

  if (!deliverables || deliverables.length === 0) {
    return (
      <div className="client-empty-state">
        <div style={{ fontSize: "2rem", marginBottom: "8px" }}>📦</div>
        <h3>No deliverables published</h3>
        <p>Your delivery team has not published any client deliverables for review yet.</p>
      </div>
    );
  }

  return (
    <div className="client-table-responsive" data-testid="client-deliverables-table">
      <table className="client-table">
        <thead>
          <tr>
            <th>Deliverable</th>
            <th>Version</th>
            <th>Asset File</th>
            <th>Submitted</th>
            <th>Status</th>
            <th>Feedback History</th>
            <th style={{ textAlign: "right" }}>Actions</th>
          </tr>
        </thead>
        <tbody>
          {deliverables.map((del) => {
            const isAccepted = (del.status || "").toUpperCase() === "ACCEPTED";
            const tone = deliverableStatusTone(del.status);

            // Latest feedback entry if present
            const latestFeedback =
              Array.isArray(del.feedbacks) && del.feedbacks.length > 0
                ? del.feedbacks[del.feedbacks.length - 1]
                : null;

            return (
              <tr key={del.deliverable_id} data-testid={`deliverable-row-${del.deliverable_id}`}>
                {/* Deliverable Info */}
                <td>
                  <div style={{ fontWeight: "600", color: "#0f172a" }}>{del.title}</div>
                  {del.description && (
                    <div
                      style={{
                        fontSize: "12px",
                        color: "#64748b",
                        maxWidth: "280px",
                        overflow: "hidden",
                        textOverflow: "ellipsis",
                        whiteSpace: "nowrap",
                      }}
                    >
                      {del.description}
                    </div>
                  )}
                </td>

                {/* Version */}
                <td>
                  <span className="deliverable-version-badge">v{del.version}</span>
                </td>

                {/* Asset Link */}
                <td>
                  {del.file_url ? (
                    <a
                      href={del.file_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      style={{
                        color: "#2563eb",
                        fontWeight: "600",
                        textDecoration: "none",
                        fontSize: "12px",
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                      }}
                    >
                      <span>Download / View</span>
                      <span aria-hidden="true">↗</span>
                    </a>
                  ) : (
                    <span style={{ color: "#94a3b8", fontSize: "12px" }}>None</span>
                  )}
                </td>

                {/* Submitted Date */}
                <td>
                  <span style={{ fontSize: "12px", color: "#64748b" }}>
                    {formatDate(del.submitted_at)}
                  </span>
                </td>

                {/* Status */}
                <td>
                  <span className={`chip chip-${tone}`}>{del.status}</span>
                </td>

                {/* Latest Feedback */}
                <td>
                  {latestFeedback ? (
                    <div style={{ fontSize: "12px" }}>
                      <div style={{ color: "#eab308", fontWeight: "700" }}>
                        {"★".repeat(latestFeedback.rating)}
                        {"☆".repeat(5 - latestFeedback.rating)}
                        <span style={{ color: "#475569", marginLeft: "4px" }}>
                          ({latestFeedback.rating}/5)
                        </span>
                      </div>
                      {latestFeedback.comments && (
                        <div
                          style={{
                            color: "#64748b",
                            fontStyle: "italic",
                            maxWidth: "220px",
                            overflow: "hidden",
                            textOverflow: "ellipsis",
                            whiteSpace: "nowrap",
                          }}
                          title={latestFeedback.comments}
                        >
                          "{latestFeedback.comments}"
                        </div>
                      )}
                    </div>
                  ) : (
                    <span style={{ color: "#94a3b8", fontSize: "12px" }}>No feedback yet</span>
                  )}
                </td>

                {/* Actions: Button is hidden when status is already ACCEPTED */}
                <td style={{ textAlign: "right" }}>
                  {isAccepted ? (
                    <span
                      style={{
                        display: "inline-flex",
                        alignItems: "center",
                        gap: "4px",
                        color: "#16a34a",
                        fontWeight: "600",
                        fontSize: "12px",
                      }}
                      title="Deliverable is approved and signed off"
                    >
                      ✓ Signed Off
                    </span>
                  ) : (
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => setSelectedDeliverable(del)}
                      data-testid={`signoff-btn-${del.deliverable_id}`}
                      style={{ padding: "6px 12px", fontSize: "12px" }}
                    >
                      Review & Sign off
                    </button>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>

      {/* Signoff Modal */}
      {selectedDeliverable && (
        <SignoffModal
          deliverable={selectedDeliverable}
          onClose={() => setSelectedDeliverable(null)}
          onSuccess={handleSignoffSuccess}
        />
      )}
    </div>
  );
}
