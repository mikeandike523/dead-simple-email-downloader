import { withAuth } from "@/server/withAuth"
import { NextApiResponse } from "next"
import { AuthedNextApiRequest } from "@/server/withAuth"

const handler = async (req: AuthedNextApiRequest, res: NextApiResponse) => {
    return res.status(200).json(req.user)
}

export default withAuth(handler)