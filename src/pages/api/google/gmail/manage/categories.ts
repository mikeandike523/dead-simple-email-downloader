import type { NextApiRequest, NextApiResponse } from "next";
import type { RowDataPacket } from "mysql2/promise";
import { getAuth } from "@/server/auth";
import { dbExec, dbQuery } from "@/server/db";

type CategoryRow = RowDataPacket & { id: number; name: string };

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  const user = await getAuth(req);
  if (!user) return res.status(401).json({ error: "unauthorized" });

  if (req.method === "GET") {
    const rows = await dbQuery<CategoryRow>(
      "SELECT id, name FROM email_categories ORDER BY name ASC"
    );
    return res.status(200).json({ categories: rows });
  }

  if (req.method === "POST") {
    const { name } = req.body ?? {};
    if (!name || typeof name !== "string") {
      return res.status(400).json({ error: "name is required" });
    }
    const normalized = name.trim().toLowerCase();
    if (!normalized) {
      return res.status(400).json({ error: "name cannot be empty" });
    }

    const existing = await dbQuery<CategoryRow>(
      "SELECT id, name FROM email_categories WHERE name = ?",
      [normalized]
    );
    if (existing.length > 0) {
      return res.status(200).json({ category: existing[0], created: false });
    }

    const result = await dbExec(
      "INSERT INTO email_categories (name) VALUES (?)",
      [normalized]
    );
    return res.status(201).json({ category: { id: result.insertId, name: normalized }, created: true });
  }

  return res.status(405).json({ error: "Method not allowed" });
}
