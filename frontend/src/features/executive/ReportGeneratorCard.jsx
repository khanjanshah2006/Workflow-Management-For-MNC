import React, { useState } from "react";
import { useToast } from "../../components/common/Toast.jsx";
import { generateReport, downloadReport } from "../../api/executiveApi.js";
import { validateReportForm } from "./executiveUtils.js";

/**
 * ReportGeneratorCard
 * Form for generating period-bounded executive management reports (PDF or CSV).
 *
 * @param {Object} props
 * @param {Function} props.onReportGenerated Callback invoked after report is created
 */
export default function ReportGeneratorCard({ onReportGenerated }) {
  const toast = useToast();

  const [maxDate] = useState(() => new Date().toISOString().split("T")[0]);

  const [formData, setFormData] = useState(() => {
    const today = new Date();
    const todayStr = today.toISOString().split("T")[0];
    const ninetyDaysAgo = new Date(today);
    ninetyDaysAgo.setDate(ninetyDaysAgo.getDate() - 90);
    const ninetyDaysAgoStr = ninetyDaysAgo.toISOString().split("T")[0];

    return {
      report_title: "",
      period_start: ninetyDaysAgoStr,
      period_end: todayStr,
      format: "PDF",
      include_department_breakdown: false,
    };
  });

  const [errors, setErrors] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [lastGeneratedReport, setLastGeneratedReport] = useState(null);
  const [isDownloading, setIsDownloading] = useState(false);

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "checkbox" ? checked : value,
    }));
    // Clear inline error on field change
    if (errors[name]) {
      setErrors((prev) => {
        const next = { ...prev };
        delete next[name];
        return next;
      });
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();

    const validation = validateReportForm(formData);
    if (!validation.isValid) {
      setErrors(validation.errors);
      return;
    }

    setErrors({});
    setIsSubmitting(true);

    try {
      const payload = {
        report_title: formData.report_title.trim(),
        period_start: formData.period_start,
        period_end: formData.period_end,
        format: formData.format,
        include_department_breakdown:
          formData.format === "PDF" ? formData.include_department_breakdown : false,
      };

      const report = await generateReport(payload);
      setLastGeneratedReport(report);
      toast.success("Report generated");

      // Notify parent to refresh or prepend to history
      if (typeof onReportGenerated === "function") {
        onReportGenerated(report);
      }
    } catch (err) {
      toast.error(err.message || "Failed to generate report.");
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDownloadLast = async () => {
    if (!lastGeneratedReport) return;
    setIsDownloading(true);
    try {
      const fallback = `${lastGeneratedReport.report_title || "executive_report"}.${lastGeneratedReport.format?.toLowerCase() || "pdf"}`;
      await downloadReport(lastGeneratedReport.report_id, fallback);
      toast.success("Download started");
    } catch (err) {
      toast.error(err.message || "Failed to download report.");
    } finally {
      setIsDownloading(false);
    }
  };

  return (
    <div className="exec-generator-card" aria-label="Management Report Generator">
      <div className="exec-card-header">
        <div>
          <h3 className="exec-card-title">Generate Management Report</h3>
          <p className="exec-card-subtitle">
            Export period-bounded executive delivery, KPI summaries, and audit logs (PDF or CSV)
          </p>
        </div>
      </div>

      <form onSubmit={handleSubmit} noValidate className="exec-form">
        {/* Report Title */}
        <div className="exec-form-group">
          <label htmlFor="report_title" className="exec-label">
            Report Title <span className="exec-required">*</span>
          </label>
          <input
            id="report_title"
            name="report_title"
            type="text"
            className={`exec-input ${errors.report_title ? "exec-input-error" : ""}`}
            placeholder="e.g. Q4 Executive Leadership Brief"
            value={formData.report_title}
            onChange={handleChange}
            maxLength={255}
            disabled={isSubmitting}
            required
          />
          {errors.report_title && (
            <span className="exec-field-error" role="alert">
              {errors.report_title}
            </span>
          )}
        </div>

        {/* Date Ranges */}
        <div className="exec-form-row">
          <div className="exec-form-group">
            <label htmlFor="period_start" className="exec-label">
              Start Date <span className="exec-required">*</span>
            </label>
            <input
              id="period_start"
              name="period_start"
              type="date"
              className={`exec-input ${errors.period_start ? "exec-input-error" : ""}`}
              value={formData.period_start}
              onChange={handleChange}
              max={maxDate}
              disabled={isSubmitting}
              required
            />
            {errors.period_start && (
              <span className="exec-field-error" role="alert">
                {errors.period_start}
              </span>
            )}
          </div>

          <div className="exec-form-group">
            <label htmlFor="period_end" className="exec-label">
              End Date <span className="exec-required">*</span>
            </label>
            <input
              id="period_end"
              name="period_end"
              type="date"
              className={`exec-input ${errors.period_end ? "exec-input-error" : ""}`}
              value={formData.period_end}
              onChange={handleChange}
              disabled={isSubmitting}
              required
            />
            {errors.period_end && (
              <span className="exec-field-error" role="alert">
                {errors.period_end}
              </span>
            )}
          </div>
        </div>

        {/* Format Selection & Options */}
        <div className="exec-form-row">
          <div className="exec-form-group">
            <label className="exec-label">Export Format</label>
            <div className="exec-radio-group">
              <label className="exec-radio-label">
                <input
                  type="radio"
                  name="format"
                  value="PDF"
                  checked={formData.format === "PDF"}
                  onChange={handleChange}
                  disabled={isSubmitting}
                />
                <span>PDF Document</span>
              </label>
              <label className="exec-radio-label">
                <input
                  type="radio"
                  name="format"
                  value="CSV"
                  checked={formData.format === "CSV"}
                  onChange={handleChange}
                  disabled={isSubmitting}
                />
                <span>CSV Spreadsheet</span>
              </label>
            </div>
            {errors.format && (
              <span className="exec-field-error" role="alert">
                {errors.format}
              </span>
            )}
          </div>

          {formData.format === "PDF" && (
            <div className="exec-form-group exec-checkbox-container">
              <label className="exec-checkbox-label">
                <input
                  type="checkbox"
                  name="include_department_breakdown"
                  checked={formData.include_department_breakdown}
                  onChange={handleChange}
                  disabled={isSubmitting}
                />
                <span>Include granular department breakdown in PDF</span>
              </label>
            </div>
          )}
        </div>

        {/* Submit Button */}
        <div className="exec-form-actions">
          <button
            type="submit"
            className="exec-primary-btn"
            disabled={isSubmitting}
          >
            {isSubmitting ? (
              <>
                <span className="exec-btn-spinner" aria-hidden="true" />
                Generating Report...
              </>
            ) : (
              "Generate Report"
            )}
          </button>
        </div>
      </form>

      {/* Success Banner with Instant Download Action */}
      {lastGeneratedReport && (
        <div className="exec-success-banner" role="status">
          <div className="exec-success-info">
            <span className="exec-success-icon" aria-hidden="true">✓</span>
            <div>
              <strong>Report ready:</strong> {lastGeneratedReport.report_title} ({lastGeneratedReport.format})
            </div>
          </div>
          <button
            type="button"
            className="exec-download-btn"
            onClick={handleDownloadLast}
            disabled={isDownloading}
          >
            {isDownloading ? "Downloading..." : "Download Now"}
          </button>
        </div>
      )}
    </div>
  );
}
