#!/bin/bash

# AuraConnect AI - Database Backup and Restore Script
# Supports both Docker Compose and Kubernetes environments

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="docker"
NAMESPACE="auraconnect"
DB_NAME="auraconnect"
DB_USER="auraconnect"
BACKUP_DIR="./backups"
S3_BUCKET=""
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Function to print colored output
print_message() {
    local color=$1
    local message=$2
    echo -e "${color}${message}${NC}"
}

# Function to show usage
usage() {
    echo "Usage: $0 [OPTIONS] COMMAND"
    echo ""
    echo "Commands:"
    echo "  backup              Create a database backup"
    echo "  restore BACKUP_FILE Restore from a backup file"
    echo "  list               List available backups"
    echo "  cleanup            Remove old backups (keeps last 7 days)"
    echo "  schedule           Setup automated backups (cron)"
    echo ""
    echo "Options:"
    echo "  -e, --env ENV      Environment (docker, kubernetes)"
    echo "  -n, --namespace NS  Kubernetes namespace (default: auraconnect)"
    echo "  -d, --database DB   Database name (default: auraconnect)"
    echo "  -u, --user USER     Database user (default: auraconnect)"
    echo "  -p, --password PASS Database password"
    echo "  -b, --backup-dir DIR Local backup directory (default: ./backups)"
    echo "  -s, --s3-bucket BUCKET S3 bucket for remote backups"
    echo "  -h, --help         Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 backup                          # Backup Docker database"
    echo "  $0 -e kubernetes backup            # Backup Kubernetes database"
    echo "  $0 restore backup_20240101.sql.gz # Restore from backup"
    echo "  $0 -s s3://my-bucket backup       # Backup and upload to S3"
}

# Function to ensure backup directory exists
ensure_backup_dir() {
    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
        print_message "$GREEN" "✓ Created backup directory: $BACKUP_DIR"
    fi
}

# Function to get database password
get_db_password() {
    if [ -z "$DB_PASSWORD" ]; then
        if [ "$ENVIRONMENT" = "docker" ]; then
            # Try to get from .env file
            if [ -f .env ]; then
                DB_PASSWORD=$(grep POSTGRES_PASSWORD .env | cut -d'=' -f2)
            fi
            
            if [ -z "$DB_PASSWORD" ]; then
                read -sp "Enter database password: " DB_PASSWORD
                echo
            fi
        elif [ "$ENVIRONMENT" = "kubernetes" ]; then
            # Get from Kubernetes secret
            DB_PASSWORD=$(kubectl get secret auraconnect-secrets -n "$NAMESPACE" \
                -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)
        fi
    fi
    
    if [ -z "$DB_PASSWORD" ]; then
        print_message "$RED" "✗ Database password not found"
        exit 1
    fi
}

# Function to backup database from Docker
backup_docker() {
    local backup_file="$BACKUP_DIR/backup_${DB_NAME}_${TIMESTAMP}.sql.gz"
    
    print_message "$BLUE" "Starting Docker database backup..."
    
    # Check if container is running
    if ! docker ps | grep -q auraconnect-postgres; then
        print_message "$RED" "✗ PostgreSQL container is not running"
        exit 1
    fi
    
    # Perform backup
    docker exec auraconnect-postgres pg_dump \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --no-owner \
        --no-acl \
        --clean \
        --if-exists | gzip > "$backup_file"
    
    local backup_size=$(du -h "$backup_file" | cut -f1)
    print_message "$GREEN" "✓ Backup created: $backup_file ($backup_size)"
    
    echo "$backup_file"
}

# Function to backup database from Kubernetes
backup_kubernetes() {
    local backup_file="$BACKUP_DIR/backup_${DB_NAME}_${TIMESTAMP}.sql.gz"
    
    print_message "$BLUE" "Starting Kubernetes database backup..."
    
    # Get PostgreSQL pod name
    local pod_name=$(kubectl get pods -n "$NAMESPACE" -l app=postgres \
        -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$pod_name" ]; then
        print_message "$RED" "✗ PostgreSQL pod not found in namespace $NAMESPACE"
        exit 1
    fi
    
    # Perform backup
    kubectl exec -n "$NAMESPACE" "$pod_name" -- pg_dump \
        -U "$DB_USER" \
        -d "$DB_NAME" \
        --no-owner \
        --no-acl \
        --clean \
        --if-exists | gzip > "$backup_file"
    
    local backup_size=$(du -h "$backup_file" | cut -f1)
    print_message "$GREEN" "✓ Backup created: $backup_file ($backup_size)"
    
    echo "$backup_file"
}

# Function to restore database to Docker
restore_docker() {
    local backup_file=$1
    
    if [ ! -f "$backup_file" ]; then
        print_message "$RED" "✗ Backup file not found: $backup_file"
        exit 1
    fi
    
    print_message "$YELLOW" "⚠ WARNING: This will overwrite the existing database!"
    read -p "Are you sure you want to continue? (yes/no): " -r
    if [ "$REPLY" != "yes" ]; then
        print_message "$RED" "✗ Restore cancelled"
        exit 1
    fi
    
    print_message "$BLUE" "Starting Docker database restore..."
    
    # Check if container is running
    if ! docker ps | grep -q auraconnect-postgres; then
        print_message "$RED" "✗ PostgreSQL container is not running"
        exit 1
    fi
    
    # Perform restore
    if [[ "$backup_file" == *.gz ]]; then
        gunzip -c "$backup_file" | docker exec -i auraconnect-postgres psql \
            -U "$DB_USER" \
            -d "$DB_NAME"
    else
        docker exec -i auraconnect-postgres psql \
            -U "$DB_USER" \
            -d "$DB_NAME" < "$backup_file"
    fi
    
    print_message "$GREEN" "✓ Database restored from: $backup_file"
}

# Function to restore database to Kubernetes
restore_kubernetes() {
    local backup_file=$1
    
    if [ ! -f "$backup_file" ]; then
        print_message "$RED" "✗ Backup file not found: $backup_file"
        exit 1
    fi
    
    print_message "$YELLOW" "⚠ WARNING: This will overwrite the existing database!"
    read -p "Are you sure you want to continue? (yes/no): " -r
    if [ "$REPLY" != "yes" ]; then
        print_message "$RED" "✗ Restore cancelled"
        exit 1
    fi
    
    print_message "$BLUE" "Starting Kubernetes database restore..."
    
    # Get PostgreSQL pod name
    local pod_name=$(kubectl get pods -n "$NAMESPACE" -l app=postgres \
        -o jsonpath='{.items[0].metadata.name}')
    
    if [ -z "$pod_name" ]; then
        print_message "$RED" "✗ PostgreSQL pod not found in namespace $NAMESPACE"
        exit 1
    fi
    
    # Perform restore
    if [[ "$backup_file" == *.gz ]]; then
        gunzip -c "$backup_file" | kubectl exec -i -n "$NAMESPACE" "$pod_name" -- psql \
            -U "$DB_USER" \
            -d "$DB_NAME"
    else
        kubectl exec -i -n "$NAMESPACE" "$pod_name" -- psql \
            -U "$DB_USER" \
            -d "$DB_NAME" < "$backup_file"
    fi
    
    print_message "$GREEN" "✓ Database restored from: $backup_file"
}

# Function to upload backup to S3
upload_to_s3() {
    local backup_file=$1
    
    if [ -z "$S3_BUCKET" ]; then
        return
    fi
    
    print_message "$BLUE" "Uploading backup to S3..."
    
    local s3_path="$S3_BUCKET/postgres-backups/$(basename "$backup_file")"
    
    if aws s3 cp "$backup_file" "$s3_path"; then
        print_message "$GREEN" "✓ Backup uploaded to: $s3_path"
        
        # Optionally remove local backup after successful upload
        # rm "$backup_file"
    else
        print_message "$RED" "✗ Failed to upload backup to S3"
    fi
}

# Function to list backups
list_backups() {
    print_message "$BLUE" "Available backups:"
    
    # Local backups
    if [ -d "$BACKUP_DIR" ]; then
        print_message "$YELLOW" "\nLocal backups ($BACKUP_DIR):"
        ls -lh "$BACKUP_DIR"/*.sql.gz 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
    fi
    
    # S3 backups
    if [ -n "$S3_BUCKET" ]; then
        print_message "$YELLOW" "\nS3 backups ($S3_BUCKET):"
        aws s3 ls "$S3_BUCKET/postgres-backups/" | awk '{print "  " $4 " (" $3 " bytes)"}'
    fi
}

# Function to cleanup old backups
cleanup_backups() {
    print_message "$BLUE" "Cleaning up old backups..."
    
    # Remove local backups older than 7 days
    if [ -d "$BACKUP_DIR" ]; then
        find "$BACKUP_DIR" -name "backup_*.sql.gz" -mtime +7 -delete
        print_message "$GREEN" "✓ Removed local backups older than 7 days"
    fi
    
    # Remove S3 backups older than 30 days
    if [ -n "$S3_BUCKET" ]; then
        local cutoff_date=$(date -d "30 days ago" +%Y-%m-%d)
        aws s3 ls "$S3_BUCKET/postgres-backups/" | while read -r line; do
            local file_date=$(echo "$line" | awk '{print $1}')
            local file_name=$(echo "$line" | awk '{print $4}')
            
            if [[ "$file_date" < "$cutoff_date" ]]; then
                aws s3 rm "$S3_BUCKET/postgres-backups/$file_name"
                print_message "$YELLOW" "  Removed S3 backup: $file_name"
            fi
        done
        print_message "$GREEN" "✓ Removed S3 backups older than 30 days"
    fi
}

# Function to setup automated backups
setup_schedule() {
    print_message "$BLUE" "Setting up automated backups..."
    
    # Create cron script
    local cron_script="/usr/local/bin/auraconnect-backup.sh"
    
    cat > /tmp/auraconnect-backup.sh << EOF
#!/bin/bash
# AuraConnect automated backup script
cd $(pwd)
$0 -e $ENVIRONMENT -n $NAMESPACE -d $DB_NAME -u $DB_USER backup
EOF
    
    sudo mv /tmp/auraconnect-backup.sh "$cron_script"
    sudo chmod +x "$cron_script"
    
    # Add to crontab (daily at 2 AM)
    local cron_entry="0 2 * * * $cron_script >> /var/log/auraconnect-backup.log 2>&1"
    
    (crontab -l 2>/dev/null | grep -v auraconnect-backup; echo "$cron_entry") | crontab -
    
    print_message "$GREEN" "✓ Automated daily backups configured (2:00 AM)"
    print_message "$YELLOW" "  Log file: /var/log/auraconnect-backup.log"
}

# Parse command line arguments
COMMAND=""
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--env)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -n|--namespace)
            NAMESPACE="$2"
            shift 2
            ;;
        -d|--database)
            DB_NAME="$2"
            shift 2
            ;;
        -u|--user)
            DB_USER="$2"
            shift 2
            ;;
        -p|--password)
            DB_PASSWORD="$2"
            shift 2
            ;;
        -b|--backup-dir)
            BACKUP_DIR="$2"
            shift 2
            ;;
        -s|--s3-bucket)
            S3_BUCKET="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        backup|restore|list|cleanup|schedule)
            COMMAND="$1"
            RESTORE_FILE="$2"
            shift
            ;;
        *)
            if [ -z "$COMMAND" ]; then
                COMMAND="$1"
            elif [ "$COMMAND" = "restore" ] && [ -z "$RESTORE_FILE" ]; then
                RESTORE_FILE="$1"
            fi
            shift
            ;;
    esac
done

# Validate environment
if [ "$ENVIRONMENT" != "docker" ] && [ "$ENVIRONMENT" != "kubernetes" ]; then
    print_message "$RED" "✗ Invalid environment: $ENVIRONMENT"
    exit 1
fi

# Execute command
case $COMMAND in
    backup)
        ensure_backup_dir
        get_db_password
        
        if [ "$ENVIRONMENT" = "docker" ]; then
            backup_file=$(backup_docker)
        else
            backup_file=$(backup_kubernetes)
        fi
        
        if [ -n "$S3_BUCKET" ]; then
            upload_to_s3 "$backup_file"
        fi
        ;;
    restore)
        if [ -z "$RESTORE_FILE" ]; then
            print_message "$RED" "✗ Please specify a backup file to restore"
            exit 1
        fi
        
        get_db_password
        
        if [ "$ENVIRONMENT" = "docker" ]; then
            restore_docker "$RESTORE_FILE"
        else
            restore_kubernetes "$RESTORE_FILE"
        fi
        ;;
    list)
        list_backups
        ;;
    cleanup)
        cleanup_backups
        ;;
    schedule)
        setup_schedule
        ;;
    *)
        print_message "$RED" "✗ Invalid command: $COMMAND"
        usage
        exit 1
        ;;
esac