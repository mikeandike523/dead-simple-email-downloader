import { withAuth } from "@/server/withAuth"
import { NextApiRequest, NextApiResponse } from "next"

const handler = async (req: NextApiRequest, res: NextApiResponse) => {
    
}

export default withAuth(handler)