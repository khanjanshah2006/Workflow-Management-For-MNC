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
      const id = n?.task_id ?? n?.entity_id ?? n?.id;
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_REASSIGNED: {
    icon: "🔄",
    label: "Task Reassigned",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = n?.task_id ?? n?.entity_id ?? n?.id;
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_DEADLINE_EXTENDED: {
    icon: "📅",
    label: "Deadline Extended",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = n?.task_id ?? n?.entity_id ?? n?.id;
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_OVERDUE: {
    icon: "⚠️",
    label: "Task Overdue",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = n?.task_id ?? n?.entity_id ?? n?.id;
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_DEADLINE_MISSED: {
    icon: "🚨",
    label: "Deadline Missed",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = n?.task_id ?? n?.entity_id ?? n?.id;
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_APPROVED: {
    icon: "✅",
    label: "Task Approved",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = n?.task_id ?? n?.entity_id ?? n?.id;
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_REJECTED: {
    icon: "❌",
    label: "Task Rejected",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = n?.task_id ?? n?.entity_id ?? n?.id;
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_COMMENT: {
    icon: "💬",
    label: "Task Comment",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = n?.task_id ?? n?.entity_id ?? n?.id;
      return id ? `/tasks?task=${id}` : "/tasks";
    },
  },
  TASK_BLOCKED: {
    icon: "🚫",
    label: "Task Blocked",
    category: NOTIFICATION_CATEGORIES.TASKS,
    route: (n) => {
      const id = n?.task_id ?? n?.entity_id ?? n?.id;
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
    route: () => "/team-lead/leave",
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
        const id = n?.project_id ?? n?.entity_id ?? n?.id;
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
      const id = n?.project_id ?? n?.entity_id ?? n?.id;
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
      const id = n?.project_id ?? n?.entity_id ?? n?.id;
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
    route: (n) => {
      const id = n?.ticket_id ?? n?.entity_id ?? n?.id;
      return id ? `/it-support?ticket=${id}` : "/it-support";
    },
  },
  TICKET_ASSIGNED: {
    icon: "🛠️",
    label: "Ticket Assigned",
    category: NOTIFICATION_CATEGORIES.SUPPORT,
    route: (n) => {
      const id = n?.ticket_id ?? n?.entity_id ?? n?.id;
      return id ? `/it-support?ticket=${id}` : "/it-support";
    },
  },
  TICKET_ESCALATED: {
    icon: "⚡",
    label: "Ticket Escalated",
    category: NOTIFICATION_CATEGORIES.SUPPORT,
    route: (n) => {
      const id = n?.ticket_id ?? n?.entity_id ?? n?.id;
      return id ? `/it-support?ticket=${id}` : "/it-support";
    },
  },
  TICKET_RESOLVED: {
    icon: "✔️",
    label: "Ticket Resolved",
    category: NOTIFICATION_CATEGORIES.SUPPORT,
    route: (n) => {
      const id = n?.ticket_id ?? n?.entity_id ?? n?.id;
      return id ? `/support/tickets?ticket=${id}` : "/support/tickets";
    },
  },
  TICKET_REOPENED: {
    icon: "🔓",
    label: "Ticket Reopened",
    category: NOTIFICATION_CATEGORIES.SUPPORT,
    route: (n) => {
      const id = n?.ticket_id ?? n?.entity_id ?? n?.id;
      return id ? `/support/tickets?ticket=${id}` : "/support/tickets";
    },
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
 * 1. Prefers backend's link field when set and non-empty.
 * 2. Otherwise calls route(notification, role) from NOTIFICATION_TYPES.
 * 3. Returns null for unknown types (mark as read only, no navigation).
 */
export function getNotificationRoute(notification, role) {
  if (!notification) return null;

  // 1. Prefer backend's link field when set
  if (notification.link && typeof notification.link === "string" && notification.link.trim() !== "") {
    return notification.link.trim();
  }

  // 2. Lookup type config
  const typeKey = notification.type ? String(notification.type).trim().toUpperCase() : "";
  const config = NOTIFICATION_TYPES[typeKey];

  if (!config || typeof config.route !== "function") {
    return null;
  }

  // 3. Resolve route via mapper
  return config.route(notification, role);
}

export default NOTIFICATION_TYPES;
