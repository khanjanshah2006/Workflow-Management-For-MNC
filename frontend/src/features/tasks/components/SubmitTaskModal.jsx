import { useState, useRef, useEffect } from "react";
import {
  submitTask,
  validateDeliverableFile,
  ALLOWED_FILE_EXTENSIONS,
} from "../../../api/tasksApi";

/**
 * Format bytes into human-readable size (e.g. "4.2 MB").
 * @param {number} bytes
 * @returns {string}
 */
function formatFileSize(bytes) {
  if (!bytes || bytes <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`;
}

/**
 * SubmitTaskModal Component (US-11)
 *
 * Allows an assigned employee to submit task deliverables for review:
 * - Remarks textarea (mandatory, non-empty)
 * - Optional drag-and-drop deliverable file attachment (max 5MB, approved extensions)
 * - Instant client-side validation and feedback
 * - Preserves form inputs on request failure
 * - Accessible dialog semantics and keyboard navigation
 *
 * @param {Object} props
 * @param {Object} props.task TaskDetailResponse object
 * @param {() => void} props.onClose Callback to close the modal
 * @param {(submission: Object) => void} props.onSuccess Callback invoked upon successful submission
 */
export default function SubmitTaskModal({ task, onClose, onSuccess }) {
  const [remarks, setRemarks] = useState("");
  const [file, setFile] = useState(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState(null);
  const [validationToast, setValidationToast] = useState(null);

  const fileInputRef = useRef(null);
  const remarksRef = useRef(null);

  // Auto-dismiss validation toast after 4s
  useEffect(() => {
    if (!validationToast) return;
    const timer = setTimeout(() => setValidationToast(null), 4000);
    return () => clearTimeout(timer);
  }, [validationToast]);

  // Focus remarks on open & handle Escape key
  useEffect(() => {
    remarksRef.current?.focus();

    const handleKeyDown = (e) => {
      if (e.key === "Escape" && !isSubmitting) {
        onClose();
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isSubmitting, onClose]);

  const handleFileSelection = (selectedFile) => {
    if (!selectedFile) return;

    setErrorMessage(null);
    const check = validateDeliverableFile(selectedFile);
    if (!check.valid) {
      setFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      setValidationToast({ type: "error", message: check.error });
      return;
    }

    setFile(selectedFile);
    setValidationToast({
      type: "success",
      message: `Attached: ${selectedFile.name} (${formatFileSize(selectedFile.size)})`,
    });
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    e.stopPropagation();
    if (!isSubmitting) {
      setIsDragging(true);
    }
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (isSubmitting) return;

    const droppedFiles = e.dataTransfer?.files;
    if (droppedFiles && droppedFiles.length > 0) {
      handleFileSelection(droppedFiles[0]);
    }
  };

  const handleRemoveFile = () => {
    setFile(null);
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMessage(null);

    const trimmedRemarks = remarks.trim();
    if (!trimmedRemarks) {
      setErrorMessage("Please provide submission remarks detailing the deliverables.");
      remarksRef.current?.focus();
      return;
    }

    if (file) {
      const check = validateDeliverableFile(file);
      if (!check.valid) {
        setErrorMessage(check.error);
        return;
      }
    }

    setIsSubmitting(true);
    try {
      const result = await submitTask(task.task_id, {
        remarks: trimmedRemarks,
        file,
      });

      if (onSuccess) {
        onSuccess(result);
      }
      onClose();
    } catch (err) {
      // Preserve form values on error (remarks and file remain in state)
      if (
        err?.status === 413 ||
        err?.message?.includes("413") ||
        err?.message?.toLowerCase().includes("larger than")
      ) {
        setErrorMessage("File is larger than 5 MB");
      } else {
        setErrorMessage(
          err.message || "Failed to submit deliverable. Please try again."
        );
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const acceptAttribute = ALLOWED_FILE_EXTENSIONS.join(",");

  return (
    <div
      className="modal-overlay"
      role="presentation"
      onClick={(e) => {
        if (e.target === e.currentTarget && !isSubmitting) {
          onClose();
        }
      }}
    >
      <div
        className="submit-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="submit-modal-title"
      >
        {/* Header */}
        <header className="modal-header">
          <div className="modal-title-group">
            <h2 id="submit-modal-title">Submit Task for Review</h2>
            <p className="modal-task-subtitle">
              Task #{task?.task_id}: {task?.title}
            </p>
          </div>
          <button
            type="button"
            className="btn-modal-close"
            onClick={onClose}
            disabled={isSubmitting}
            aria-label="Close submission modal"
          >
            ✕
          </button>
        </header>

        {/* Form Body */}
        <form onSubmit={handleSubmit} noValidate>
          <div className="modal-body">
            {/* Transient Instant Feedback Toast */}
            {validationToast && (
              <div
                className={`tasks-toast ${
                  validationToast.type === "error"
                    ? "toast-error"
                    : "toast-success"
                }`}
                style={{ position: "static", marginBottom: 0, width: "100%" }}
                role="status"
              >
                <span aria-hidden="true">
                  {validationToast.type === "error" ? "⚠️" : "✓"}
                </span>
                <span>{validationToast.message}</span>
              </div>
            )}

            {/* API / Validation Error Banner */}
            {errorMessage && (
              <div
                className="drawer-alert drawer-alert-blocked"
                role="alert"
                style={{ margin: 0 }}
              >
                <span className="drawer-alert-icon" aria-hidden="true">
                  ⚠️
                </span>
                <div className="drawer-alert-content">
                  <div className="drawer-alert-title">Submission Error</div>
                  <div>{errorMessage}</div>
                </div>
              </div>
            )}

            {/* Remarks Input */}
            <div className="form-group">
              <label htmlFor="submit-remarks" className="form-label">
                <span>Submission Remarks <span style={{ color: "#dc2626" }}>*</span></span>
                <span style={{ fontSize: 11, fontWeight: 500, color: "#64748b" }}>
                  {remarks.length} characters
                </span>
              </label>
              <textarea
                id="submit-remarks"
                ref={remarksRef}
                className="form-textarea"
                rows={4}
                placeholder="Describe the work completed, deliverables attached, or testing performed..."
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                disabled={isSubmitting}
                required
                aria-required="true"
              />
            </div>

            {/* File Upload / Drag-and-Drop Area */}
            <div className="form-group">
              <label className="form-label">
                <span>Deliverable Attachment (Optional)</span>
                <span style={{ fontSize: 11, fontWeight: 500, color: "#64748b" }}>
                  Max 5 MB
                </span>
              </label>

              <input
                ref={fileInputRef}
                type="file"
                accept={acceptAttribute}
                onChange={(e) => {
                  if (e.target.files && e.target.files[0]) {
                    handleFileSelection(e.target.files[0]);
                  }
                }}
                disabled={isSubmitting}
                style={{ display: "none" }}
                id="submit-file-input"
              />

              {!file ? (
                <div
                  className={`file-dropzone ${isDragging ? "dragging" : ""}`}
                  onDragOver={handleDragOver}
                  onDragLeave={handleDragLeave}
                  onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      fileInputRef.current?.click();
                    }
                  }}
                  aria-label="Upload deliverable file. Click or drag and drop a file here."
                >
                  <div className="file-dropzone-icon" aria-hidden="true">
                    📁
                  </div>
                  <p className="file-dropzone-text">
                    <strong>Click to browse</strong> or drag and drop deliverable
                  </p>
                  <p className="file-dropzone-hint">
                    Supported: PDF, ZIP, TAR.GZ, PNG, JPG, JPEG, DOCX (up to 5MB)
                  </p>
                </div>
              ) : (
                <div className="file-preview-card">
                  <div className="file-preview-info">
                    <span className="file-preview-icon" aria-hidden="true">
                      📄
                    </span>
                    <div>
                      <div className="file-preview-name" title={file.name}>
                        {file.name}
                      </div>
                      <div className="file-preview-size">
                        {formatFileSize(file.size)}
                      </div>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-file-remove"
                    onClick={handleRemoveFile}
                    disabled={isSubmitting}
                    aria-label={`Remove file ${file.name}`}
                    title="Remove attachment"
                  >
                    ✕
                  </button>
                </div>
              )}
            </div>
          </div>

          {/* Footer */}
          <footer className="modal-footer">
            <button
              type="button"
              className="btn-modal-cancel"
              onClick={onClose}
              disabled={isSubmitting}
            >
              Cancel
            </button>
            <button
              type="submit"
              className="btn-modal-submit"
              disabled={isSubmitting || !remarks.trim()}
            >
              {isSubmitting ? "Submitting Deliverable..." : "Submit for Review"}
            </button>
          </footer>
        </form>
      </div>
    </div>
  );
}
