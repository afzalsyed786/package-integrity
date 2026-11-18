import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { api, errMsg } from "./api";

export function useAnalysisJob() {
  const [job, setJob] = useState(null);
  const timer = useRef(null);
  const navigate = useNavigate();

  useEffect(() => {
    const ref = timer;
    return () => clearInterval(ref.current);
  }, []);

  const start = async (body) => {
    clearInterval(timer.current);
    try {
      const { data } = await api.post("/analyses", body);
      setJob(data);
      timer.current = setInterval(async () => {
        let j;
        try {
          ({ data: j } = await api.get(`/jobs/${data.id}`));
        } catch (e) {
          clearInterval(timer.current);
          setJob(null);
          toast.error(`Lost track of analysis: ${errMsg(e)}`);
          return;
        }
        setJob(j);
        if (j.status === "completed") {
          clearInterval(timer.current);
          toast.success(`${body.name}: ${j.verdict}`);
          navigate(`/analyses/${j.analysis_id}`);
        } else if (j.status === "failed") {
          clearInterval(timer.current);
          toast.error(j.error);
        }
      }, 900);
    } catch (e) {
      toast.error(errMsg(e));
    }
  };

  return { job, start, running: job?.status === "running" };
}
