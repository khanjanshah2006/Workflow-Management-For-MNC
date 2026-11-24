import {
  ROLES,
  INTERNAL_ROLES,
  PLATFORM_ADMINS,
  IT_STAFF,
  normalizeRole,
  getUserRole,
  getHomeRouteForRole,
} from "../../auth/session.js";

export { ROLES, INTERNAL_ROLES, PLATFORM_ADMINS, IT_STAFF, getHomeRouteForRole };

/**
 * Shared navigation configuration for WorkSphere application.
 *
 * Each entry conforms to:
 * {
 *   path: string,
 *   label: string,
 *   icon: string,
 *   roles: string[] | null // null = shared across all authenticated roles
 * }
 */
export const navConfig = [
  {
    path: "/dashboard",
    label: "Dashboard",
    icon: "▦",
    roles: INTERNAL_ROLES,
  },
  {
    path: "/projects",
    label: "Projects",
    icon: "◇",
    roles: [ROLES.PM, ROLES.ADMIN],
  },
  {
    path: "/pm/risk-dashboard",
    label: "Risk Dashboard",
    icon: "⚠️",
    roles: [ROLES.PM, ROLES.ADMIN],
  },
  {
    path: "/team",
    label: "Team Roster",
    icon: "👥",
    roles: INTERNAL_ROLES,
  },
  {
    path: "/tasks",
    label: "Tasks",
    icon: "✓",
    roles: INTERNAL_ROLES,
  },
  {
    path: "/team-lead/tasks",
    label: "Team Tasks",
    icon: "📋",
    roles: [ROLES.TEAM_LEAD, ROLES.PM, ROLES.ADMIN],
  },
  {
    path: "/leave",
    label: "Leave",
    icon: "🗓️",
    roles: [ROLES.EMPLOYEE, ROLES.TEAM_LEAD],
  },
  {
    path: "/team-lead/leave",
    label: "Leave Triage",
    icon: "⚖️",
    roles: [ROLES.TEAM_LEAD, ROLES.HR, ROLES.ADMIN],
  },
  {
    path: "/hr/leave-policies",
    label: "Leave Policies",
    icon: "📜",
    roles: [ROLES.HR, ROLES.ADMIN],
  },
  {
    path: "/skill-requests",
    label: "Skill Requests",
    icon: "🎯",
    roles: [ROLES.HR, ROLES.TEAM_LEAD, ROLES.ADMIN, ROLES.SYSTEM_ADMIN],
  },
  {
    path: "/it-support",
    label: "IT Support",
    icon: "🛠",
    roles: IT_STAFF,
  },
  {
    path: "/profile",
    label: "My Profile",
    icon: "○",
    roles: INTERNAL_ROLES,
  },
  {
    path: "/admin/users",
    label: "User Admin",
    icon: "👤",
    roles: PLATFORM_ADMINS,
  },
  {
    path: "/admin/security",
    label: "Security Ops",
    icon: "🛡️",
    roles: PLATFORM_ADMINS,
  },
  {
    path: "/executive/console",
    label: "Executive Console",
    icon: "📊",
    roles: [ROLES.MNC_EXECUTIVE, ROLES.ADMIN, ROLES.SYSTEM_ADMIN],
  },
];

/**
 * Filters navigation items based on the provided user role.
 *
 * Requirements:
 * - A user sees only navigation entries permitted for their role.
 * - Shared navigation entries (roles: null) remain visible where appropriate.
 * - A missing or unknown role must not accidentally expose privileged navigation.
 * - Pure and deterministic: does not mutate the input array or its objects.
 *
 * @param {Array<Object>} config Array of navigation items
 * @param {string|Object|null|undefined} roleOrUser User role string, user object, or null
 * @returns {Array<Object>} Filtered list of visible navigation items
 */
export function filterNavForRole(config, roleOrUser) {
  if (!Array.isArray(config)) {
    return [];
  }

  const normRole = getUserRole(roleOrUser);
  const isValidRole = normRole === ROLES.CLIENT || INTERNAL_ROLES.includes(normRole);

  // Missing, null, empty or unknown roles return an empty array (strictly fail-closed)
  if (!isValidRole) {
    return [];
  }

  return config.filter((item) => {
    if (!item || typeof item !== "object") return false;

    // Only roles: null explicitly designates shared navigation for authenticated roles
    if (item.roles === null) {
      return true;
    }

    // roles: undefined, missing roles property, or malformed non-array roles must NOT expose the entry
    if (!Array.isArray(item.roles)) {
      return false;
    }

    return item.roles.some((allowed) => {
      const normAllowed = normalizeRole(allowed);
      return normAllowed === normRole;
    });
  });
}
