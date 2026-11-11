/**
 * TicketFilterBar Component (US-27: IT Support Triage Queue)
 *
 * Provides responsive multi-dimensional filtering for incoming IT support tickets:
 * - Category filter (hardware, software, network, access, other)
 * - Status filter (open, in_progress, resolved, escalated)
 * - Priority filter (critical, high, medium, low)
 * - Text search (ticket number, subject, reporter)
 */

const CATEGORY_OPTIONS = [
  { value: "ALL", label: "All Categories" },
  { value: "hardware", label: "Hardware" },
  { value: "software", label: "Software" },
  { value: "network", label: "Network" },
  { value: "access", label: "Access & IAM" },
  { value: "other", label: "Other" },
];

const STATUS_OPTIONS = [
  { value: "ALL", label: "All Statuses" },
  { value: "open", label: "Open" },
  { value: "in_progress", label: "In Progress" },
  { value: "resolved", label: "Resolved" },
  { value: "escalated", label: "Escalated" },
];

const PRIORITY_OPTIONS = [
  { value: "ALL", label: "All Priorities" },
  { value: "CRITICAL", label: "Critical" },
  { value: "HIGH", label: "High" },
  { value: "MEDIUM", label: "Medium" },
  { value: "LOW", label: "Low" },
];

export default function TicketFilterBar({
  categoryFilter,
  onCategoryChange,
  statusFilter,
  onStatusChange,
  priorityFilter,
  onPriorityChange,
  searchQuery,
  onSearchChange,
  onResetFilters,
  totalCount,
  filteredCount,
}) {
  const hasActiveFilters =
    categoryFilter !== "ALL" ||
    statusFilter !== "ALL" ||
    priorityFilter !== "ALL" ||
    searchQuery.trim().length > 0;

  return (
    <div className="ticket-filter-bar" role="search" aria-label="Support ticket filters">
      <div className="filter-search-group">
        <div className="search-input-wrapper">
          <span className="search-icon" aria-hidden="true">🔍</span>
          <input
            type="search"
            className="filter-search-input"
            placeholder="Search tickets by #, subject, or requester..."
            value={searchQuery}
            onChange={(e) => onSearchChange(e.target.value)}
            aria-label="Search support tickets"
          />
          {searchQuery && (
            <button
              type="button"
              className="clear-search-btn"
              onClick={() => onSearchChange("")}
              aria-label="Clear search input"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      <div className="filter-selects-group">
        {/* Category Filter */}
        <div className="filter-field">
          <label htmlFor="filter-category" className="filter-label">Category</label>
          <select
            id="filter-category"
            className="filter-select"
            value={categoryFilter}
            onChange={(e) => onCategoryChange(e.target.value)}
          >
            {CATEGORY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Status Filter */}
        <div className="filter-field">
          <label htmlFor="filter-status" className="filter-label">Status</label>
          <select
            id="filter-status"
            className="filter-select"
            value={statusFilter}
            onChange={(e) => onStatusChange(e.target.value)}
          >
            {STATUS_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Priority Filter */}
        <div className="filter-field">
          <label htmlFor="filter-priority" className="filter-label">Priority</label>
          <select
            id="filter-priority"
            className="filter-select"
            value={priorityFilter}
            onChange={(e) => onPriorityChange(e.target.value)}
          >
            {PRIORITY_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        </div>

        {/* Reset Filters Button */}
        {hasActiveFilters && (
          <button
            type="button"
            className="btn-reset-filters"
            onClick={onResetFilters}
            title="Reset all filters to defaults"
          >
            Reset Filters
          </button>
        )}
      </div>

      <div className="filter-results-meta">
        <span className="results-badge">
          Showing <strong>{filteredCount}</strong> of <strong>{totalCount}</strong> tickets
        </span>
      </div>
    </div>
  );
}
