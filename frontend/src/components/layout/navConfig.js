import { normalizeRole, getUserRole, INTERNAL_ROLES, getHomeRouteForRole } from "../../auth/session.js";

export { INTERNAL_ROLES, getHomeRouteForRole };

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
    roles: ["PM", "PROJECT_MANAGER", "SYSTEM_ADMIN", "ADMIN"],
  },
  {
    path: "/pm/risk-dashboard",
    label: "Risk Dashboard",
    icon: "⚠️",
    roles: ["PM", "PROJECT_MANAGER", "SYSTEM_ADMIN", "ADMIN"],
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
    roles: ["TEAM_LEAD", "PM", "PROJECT_MANAGER", "SYSTEM_ADMIN", "ADMIN"],
  },
  {
    path: "/support",
    label: "IT Support",
    icon: "🛠",
    roles: INTERNAL_ROLES,
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
    roles: ["SYSTEM_ADMIN", "ADMIN"],
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
  const isValidRole = normRole === "CLIENT" || INTERNAL_ROLES.includes(normRole);

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
      // Support PM <-> PROJECT_MANAGER alias
      if (
        (normAllowed === "PM" || normAllowed === "PROJECT_MANAGER") &&
        (normRole === "PM" || normRole === "PROJECT_MANAGER")
      ) {
        return true;
      }
      return normAllowed === normRole;
    });
  });
}
