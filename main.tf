
provider "aws" {
  region = "us-west-2"  
}


terraform {
  backend "s3" {
    bucket         = "terraform-state" # create your own bucket
    key            = "expenses/terraform.tfstate"
    region         = "us-west-2"
    
    encrypt        = true
    use_lockfile = true
  }
}




# VPC (using default)
data "aws_vpc" "default" {
  default = true
}

# Subnet (using first available subnet in the VPC)
data "aws_subnet" "default" {
  vpc_id = data.aws_vpc.default.id
  availability_zone = "us-west-2a"  # Change this to your preferred AZ
}

# Security Group
resource "aws_security_group" "app_sg" {
  name        = "app_sg"
  description = "Security group for FastAPI app"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# EC2 Instance
resource "aws_instance" "app_server" {
  ami           = "ami-07d9cf938edb0739b"  
  instance_type = "t2.micro"
  

  vpc_security_group_ids = [aws_security_group.app_sg.id]
  subnet_id              = data.aws_subnet.default.id

  tags = {
    Name = "FastAPI-App-Server"
  }

  user_data = <<-EOF
              #!/bin/bash
              sudo yum update -y
              sudo yum install -y python3 python3-pip git nginx
        
              # Clone github repo
              
              git clone https://github.com/rblcoder/expense_tracker.git
              cd expense_tracker
              pip install -r requirements.txt
              sudo nohup uvicorn main:app --host 0.0.0.0 --port 8000 &
               # Configure Nginx
              sudo tee /etc/nginx/conf.d/fastapi_proxy.conf > /dev/null <<EOT
              server {
                  listen 80;
                  server_name _;

                  location / {
                      proxy_pass http://127.0.0.1:8000;
                      proxy_set_header Host \$host;
                      proxy_set_header X-Real-IP \$remote_addr;
                  }
              }
              EOT

              sudo systemctl enable nginx
              sudo systemctl start nginx

              EOF
}

# Elastic IP
resource "aws_eip" "app_eip" {
  instance = aws_instance.app_server.id
  domain   = "vpc"
}


# Outputs
output "app_server_public_ip" {
  value = aws_eip.app_eip.public_ip
}

