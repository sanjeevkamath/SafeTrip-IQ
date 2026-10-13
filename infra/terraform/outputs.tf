output "ecr_repository_url" { value = aws_ecr_repository.worker.repository_url }
output "model_bucket" { value = aws_s3_bucket.models.bucket }
output "ecs_cluster" { value = aws_ecs_cluster.worker.name }
output "subnet_id" { value = aws_subnet.worker.id }
output "security_group_id" { value = aws_security_group.worker.id }
output "benchmark_task_arns" {
  value = { for name, task in aws_ecs_task_definition.benchmark : name => task.arn }
}
