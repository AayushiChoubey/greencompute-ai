from app.bigquery_client import BigQueryClient
from app.batch_client import CloudBatchAdapter
from app.explainer import DecisionExplainer
from app.prompt_parser import PromptParser
from app.workflow_client import WorkflowExecutionAdapter

# Client Singletons
bq_client = BigQueryClient()
batch_adapter = CloudBatchAdapter()
explainer = DecisionExplainer()
prompt_parser = PromptParser()
workflow_adapter = WorkflowExecutionAdapter()