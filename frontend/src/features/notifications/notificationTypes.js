import { ROLES } from "../../auth/session.js";

/**
 * High-level notification categories for filtering on /notifications
 */
export const NOTIFICATION_CATEGORIES = Object.freeze({
  ALL: "All",
  TASKS: "Tasks",
  LEAVE: "Leave",
  TEAMS_SKILLS: "Teams & Skills",
  SUPPORT: "Support",
  SECURITY: "Security",
  PROJECTS_CLIENTS: "Projects & Clients",
});

export const NOTIFICATION_CATEGORY_LIST = Object.freeze([
  NOTIFICATION_CATEGORIES.ALL,
  NOTIFICATION_CATEGORIES.TASKS,
  NOTIFICATION_CATEGORIES.LEAVE,
  NOTIFICATION_CATEGORIES.TEAMS_SKILLS,
  NOTIFICATION_CATEGORIES.SUPPORT,
  NOTIFICATION_CATEGORIES.SECURITY,
  NOTIFICATION_CATEGORIES.PROJECTS_CLIENTS,
]);

/**
 * Extracts a numeric entity id from the backend `link`, e.g. "/tasks/11",
 * "/api/v1/tasks/11/submissions" or "/projects/4/deliverables".
 * The notification's own `id` is a UUID and must never be used as an entity id.
 */
export function getLinkedEntityId(notification, segment) {
  const link = typeof notification?.link === "string" ? notification.link : "";
  const match = new RegExp(`/${segment}/(\\d+)(?:[/?#]|$)`).exec(link);
  return match ? match[1] : null;
}

/**
 * Parses a backend timestamp. The API returns naive UTC datetimes
 * (no "Z" or offset), which `new Date()` would otherwise read as local time.
 */
export function parseServerDate(value) {
  if (!value) return null;
  if (value instanceof Date) return value;
  const text = String(value).trim();
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(text);
  const isDateTime = /^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}/.test(text);
  return new Date(isDateTime && !hasZone ? `${text.replace(" ", "T")}Z` : text);
}

/**
 * Master mapping for all notification types across the application (US-19).
 * Defines icon, human-readable label, category, and target route.
 */
export const NOTIFICATION_TYPES = Object.freeze({
  // Tasks (11 types)
  TASK_ASSIGNED: {
    icon: "📋",
    label: "Task Assigned",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = getLinkedEntityId(n, "tasks");
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_REASSIGNED: {
    icon: "🔄",
    label: "Task Reassigned",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = getLinkedEntityId(n, "tasks");
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_DEADLINE_EXTENDED: {
    icon: "📅",
    label: "Deadline Extended",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = getLinkedEntityId(n, "tasks");
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_OVERDUE: {
    icon: "⚠️",
    label: "Task Overdue",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = getLinkedEntityId(n, "tasks");
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_DEADLINE_MISSED: {
    icon: "🚨",
    label: "Deadline Missed",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = getLinkedEntityId(n, "tasks");
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_APPROVED: {
    icon: "✅",
    label: "Task Approved",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = getLinkedEntityId(n, "tasks");
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_REJECTED: {
    icon: "❌",
    label: "Task Rejected",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = getLinkedEntityId(n, "tasks");
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_COMMENT: {
    icon: "💬",
    label: "Task Comment",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = getLinkedEntityId(n, "tasks");
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_BLOCKED: {
    icon: "🚫",
    label: "Task Blocked",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = getLinkedEntityId(n, "tasks");
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_SUBMITTED: {
    icon: "📤",
    label: "Task Submitted",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: () => "/team-lead/tasks?tab=review",
  },
  TASK_RESUBMITTED: {
    icon: "🔄",
    label: "Task Resubmitted",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: () => "/team-lead/tasks?tab=review",
  },

  // Leave (4 types)
  LEAVE_REQUESTED: {
    icon: "🏖️",
    label: "Leave Requested",
    category: NOTIFICATION_CATEGORIES.LEAVE,
    route: (n) => {
      const match = /[?&]request=(\d+)/.exec(typeof n?.link === "string" ? n.link : "");
      return match ? `/team-lead/leave?request=${match[1]}` : "/team-lead/leave";
    },
  },
  LEAVE_APPROVED: {
    icon: "✅",
    label: "Leave Approved",
    category: NOTIFICATION_CATEGORIES.LEAVE,
    route: () => "/leave",
  },
  LEAVE_REJECTED: {
    icon: "❌",
    label: "Leave Rejected",
    category: NOTIFICATION_CATEGORIES.LEAVE,
    route: () => "/leave",
  },
  STAFF_LEAVE_APPROVED: {
    icon: "👥",
    label: "Staff Leave Approved",
    category: NOTIFICATION_CATEGORIES.LEAVE,
    route: () => "/leave",
  },

  // Projects & Clients (3 types)
  PROJECT_ASSIGNED: {
    icon: "💼",
    label: "Project Assigned",
    category: NOTIFICATION_CATEGORIES.PROJECTS_CLIENTS,
    route: (n, role) => {
      const upperRole = (role || "").toUpperCase();
      const isPmOrAdmin =
        upperRole === ROLES.PM ||
        upperRole === ROLES.ADMIN ||
        upperRole === ROLES.SYSTEM_ADMIN;
      if (isPmOrAdmin) {
        const id = getLinkedEntityId(n, "projects");
        return id ? `/projects/${id}` : "/projects";
      }
      return "/tasks";
    },
  },
  DELIVERABLE_SHARED: {
    icon: "📦",
    label: "Deliverable Shared",
    category: NOTIFICATION_CATEGORIES.PROJECTS_CLIENTS,
    route: (n, role) => {
      const isClientRole = (role || "").toUpperCase() === ROLES.CLIENT;
      const id = getLinkedEntityId(n, "projects");
      if (isClientRole) {
        return id ? `/client/projects/${id}` : "/client/projects";
      }
      return id ? `/projects/${id}` : "/projects";
    },
  },
  DELIVERABLE_FEEDBACK: {
    icon: "📝",
    label: "Deliverable Feedback",
    category: NOTIFICATION_CATEGORIES.PROJECTS_CLIENTS,
    route: (n, role) => {
      const isClientRole = (role || "").toUpperCase() === ROLES.CLIENT;
      const id = getLinkedEntityId(n, "projects");
      if (isClientRole) {
        return id ? `/client/projects/${id}` : "/client/projects";
      }
      return id ? `/projects/${id}` : "/projects";
    },
  },

  // Teams & Skills (4 types)
  TEAM_MEMBER_ADDED: {
    icon: "👤",
    label: "Team Member Added",
    category: NOTIFICATION_CATEGORIES.TEAMS_SKILLS,
    route: () => "/team/roster",
  },
  TEAM_LEAD_ASSIGNED: {
    icon: "⭐",
    label: "Team Lead Assigned",
    category: NOTIFICATION_CATEGORIES.TEAMS_SKILLS,
    route: () => "/team/roster",
  },
  SKILL_REQUEST_CREATED: {
    icon: "💡",
    label: "Skill Request Created",
    category: NOTIFICATION_CATEGORIES.TEAMS_SKILLS,
    route: () => "/skill-requests",
  },
  SKILL_REQUEST_DECIDED: {
    icon: "🎓",
    label: "Skill Request Decided",
    category: NOTIFICATION_CATEGORIES.TEAMS_SKILLS,
    route: () => "/profile",
  },

  // Support (5 types)
  TICKET_CREATED: {
    icon: "🎫",
    label: "Ticket Created",
    category: NOTIFICATION_CATEGORIES.SUPPORT,
    route: () => "/it-support",
  },
  TICKET_ASSIGNED: {
    icon: "🛠️",
    label: "Ticket Assigned",
    category: NOTIFICATION_CATEGORIES.SUPPORT,
    route: () => "/it-support",
  },
  TICKET_ESCALATED: {
    icon: "⚡",
    label: "Ticket Escalated",
    category: NOTIFICATION_CATEGORIES.SUPPORT,
    route: () => "/it-support",
  },
  TICKET_RESOLVED: {
    icon: "✔️",
    label: "Ticket Resolved",
    category: NOTIFICATION_CATEGORIES.SUPPORT,
    route: () => "/support/tickets",
  },
  TICKET_REOPENED: {
    icon: "🔓",
    label: "Ticket Reopened",
    category: NOTIFICATION_CATEGORIES.SUPPORT,
    route: () => "/support/tickets",
  },

  // Security (4 types)
  SECURITY_ALERT: {
    icon: "🛡️",
    label: "Security Alert",
    category: NOTIFICATION_CATEGORIES.SECURITY,
    route: () => "/admin/security",
  },
  ACCOUNT_UNLOCKED: {
    icon: "🔑",
    label: "Account Unlocked",
    category: NOTIFICATION_CATEGORIES.SECURITY,
    route: () => "/account/security",
  },
  ELEVATED_ACCESS_GRANTED: {
    icon: "🔐",
    label: "Elevated Access Granted",
    category: NOTIFICATION_CATEGORIES.SECURITY,
    route: () => "/dashboard",
  },
  ELEVATED_ACCESS_REVOKED: {
    icon: "🔒",
    label: "Elevated Access Revoked",
    category: NOTIFICATION_CATEGORIES.SECURITY,
    route: () => "/dashboard",
  },
});

/**
 * Fallback configuration for unrecognized or future notification types.
 */
export const UNKNOWN_NOTIFICATION_TYPE = Object.freeze({
  icon: "🔔",
  label: "Notification",
  category: "Other",
  route: () => null,
});

/**
 * Looks up type config or returns the generic fallback.
 */
export function getNotificationConfig(type) {
  if (!type) return UNKNOWN_NOTIFICATION_TYPE;
  const normalized = String(type).trim().toUpperCase();
  return NOTIFICATION_TYPES[normalized] || UNKNOWN_NOTIFICATION_TYPE;
}

/**
 * Determines the target route for a notification.
 * 1. Mapped types always resolve via route(notification, role). Backend links
 *    are often API or legacy paths (e.g. "/tasks/11", "/leave/requests/3")
 *    that are not frontend routes, so they only supply the entity id.
 * 2. Unmapped types fall back to the backend's link field when set.
 * 3. Otherwise returns null (mark as read only, no navigation).
 */
export function getNotificationRoute(notification, role) {
  if (!notification) return null;

  const typeKey = notification.type ? String(notification.type).trim().toUpperCase() : "";
  const config = NOTIFICATION_TYPES[typeKey];

  if (config && typeof config.route === "function") {
    return config.route(notification, role);
  }

  if (typeof notification.link === "string" && notification.link.trim() !== "") {
    return notification.link.trim();
  }

  return null;
}

export default NOTIFICATION_TYPES;
