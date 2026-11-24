import { ROLES } from "./session.js";

/**
 * Demo accounts for quick email filling in development mode.
 * Contains NO passwords; the quick fill button populates the email field only.
 */
export const DEMO_USERS = Object.freeze({
  "admin@company.com": {
    email: "admin@company.com",
    role: ROLES.ADMIN,
    label: "Admin (Company)",
  },
  "sysadmin@company.com": {
    email: "sysadmin@company.com",
    role: ROLES.SYSTEM_ADMIN,
    label: "SysAdmin (Company)",
  },
  "pm@company.com": {
    email: "pm@company.com",
    role: ROLES.PM,
    label: "PM (Company)",
  },
  "john.teamlead@company.com": {
    email: "john.teamlead@company.com",
    role: ROLES.TEAM_LEAD,
    label: "Team Lead (John)",
  },
  "sarah.connor@company.com": {
    email: "sarah.connor@company.com",
    role: ROLES.EMPLOYEE,
    label: "Employee (Sarah)",
  },
  "hr@company.com": {
    email: "hr@company.com",
    role: ROLES.HR,
    label: "HR (Company)",
  },
  "it.support@company.com": {
    email: "it.support@company.com",
    role: ROLES.IT_SUPPORT,
    label: "IT Support",
  },
  "executive@company.com": {
    email: "executive@company.com",
    role: ROLES.MNC_EXECUTIVE,
    label: "MNC Executive",
  },
  "client@acme.com": {
    email: "client@acme.com",
    role: ROLES.CLIENT,
    label: "Client (Acme)",
  },
  "admin@worksphere.com": {
    email: "admin@worksphere.com",
    role: ROLES.SYSTEM_ADMIN,
    label: "SysAdmin (WorkSphere)",
  },
  "pm@worksphere.com": {
    email: "pm@worksphere.com",
    role: ROLES.PM,
    label: "PM (WorkSphere)",
  },
  "employee@worksphere.com": {
    email: "employee@worksphere.com",
    role: ROLES.EMPLOYEE,
    label: "Employee (WorkSphere)",
  },
  "hr@worksphere.com": {
    email: "hr@worksphere.com",
    role: ROLES.HR,
    label: "HR (WorkSphere)",
  },
  "client@worksphere.com": {
    email: "client@worksphere.com",
    role: ROLES.CLIENT,
    label: "Client (WorkSphere)",
  },
});

export default DEMO_USERS;
