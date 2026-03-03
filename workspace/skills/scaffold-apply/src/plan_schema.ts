export type PlanStep = {
  file: string;
  operation: "create" | "patch" | "delete";
  content?: string;
  rationale: string;
};

export type PlanInput = {
  dry_run?: boolean;
  target_dir: string;
  plan: PlanStep[];
};

export const planSchema = {
  $schema: "https://json-schema.org/draft/2020-12/schema",
  type: "object",
  required: ["target_dir", "plan"],
};

function hasTraversal(file: string): boolean {
  if (file.startsWith("/")) return true;
  const parts = file.split(/[\\/]+/g);
  return parts.includes("..");
}

export function validatePlanInput(value: any): { valid: boolean; errors: string[] } {
  const errors: string[] = [];
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return { valid: false, errors: ["input must be an object"] };
  }
  if (value.dry_run !== undefined && typeof value.dry_run !== "boolean") {
    errors.push("dry_run must be boolean");
  }
  if (typeof value.target_dir !== "string" || value.target_dir.trim().length === 0) {
    errors.push("target_dir is required and must be a non-empty string");
  }
  if (!Array.isArray(value.plan)) {
    errors.push("plan must be an array");
  } else {
    value.plan.forEach((step: any, index: number) => {
      if (!step || typeof step !== "object" || Array.isArray(step)) {
        errors.push(`plan[${index}] must be an object`);
        return;
      }
      if (typeof step.file !== "string" || step.file.trim().length === 0) {
        errors.push(`plan[${index}].file must be a non-empty string`);
      } else if (hasTraversal(step.file)) {
        errors.push(`plan[${index}].file must not escape target_dir`);
      }
      if (!["create", "patch", "delete"].includes(step.operation)) {
        errors.push(`plan[${index}].operation must be create|patch|delete`);
      }
      if (typeof step.rationale !== "string" || step.rationale.trim().length === 0) {
        errors.push(`plan[${index}].rationale must be a non-empty string`);
      }
      if ((step.operation === "create" || step.operation === "patch") && typeof step.content !== "string") {
        errors.push(`plan[${index}].content must be a string for ${step.operation}`);
      }
      if (step.operation === "delete" && step.content !== undefined && typeof step.content !== "string") {
        errors.push(`plan[${index}].content must be string when provided`);
      }
    });
  }
  return { valid: errors.length === 0, errors };
}
