import { test, describe } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SRC_DIR = path.resolve(__dirname, "../src");

const FORBIDDEN_PATTERN = /\b(HR_MANAGER|PROJECT_MANAGER)\b/;

function getFilesRecursively(dir) {
  let results = [];
  const list = fs.readdirSync(dir);
  for (const file of list) {
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat && stat.isDirectory()) {
      results = results.concat(getFilesRecursively(fullPath));
    } else if (/\.(js|jsx|ts|tsx|json|css|html)$/.test(file)) {
      results.push(fullPath);
    }
  }
  return results;
}

describe("Canonical Roles Enforcement (No HR_MANAGER or PROJECT_MANAGER)", () => {
  test("src/ directory contains zero occurrences of HR_MANAGER or PROJECT_MANAGER", () => {
    const files = getFilesRecursively(SRC_DIR);
    assert.ok(files.length > 0, "Expected to find source files in src/");

    const violations = [];

    for (const filePath of files) {
      const content = fs.readFileSync(filePath, "utf-8");
      const lines = content.split("\n");
      lines.forEach((line, index) => {
        if (FORBIDDEN_PATTERN.test(line)) {
          violations.push({
            file: path.relative(SRC_DIR, filePath),
            line: index + 1,
            snippet: line.trim(),
          });
        }
      });
    }

    if (violations.length > 0) {
      const details = violations
        .map((v) => `  ${v.file}:${v.line} -> ${v.snippet}`)
        .join("\n");
      assert.fail(`Found forbidden legacy role names (HR_MANAGER / PROJECT_MANAGER) in src/:\n${details}`);
    }

    assert.equal(violations.length, 0);
  });
});
