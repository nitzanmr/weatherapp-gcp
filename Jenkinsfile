pipeline {
    agent {
        kubernetes {
            cloud 'eks_cluster'
            inheritFrom 'k8s-agent'
            yaml '''
            apiVersion: v1
            kind: Pod
            spec:
              containers:
              - name: build
                image: nitzanm594/jenkins_machine:alpine
                command:
                - cat
                tty: true
              - name: buildkit
                image: moby/buildkit:latest
                command:
                - cat
                tty: true
                env:
                - name: BUILDKITD_FLAGS
                  value: --oci-worker-no-process-sandbox
                securityContext:
                  privileged: true
                volumeMounts:
                - name: shared-tmp
                  mountPath: /tmp
              volumes:
              - name: shared-tmp
                emptyDir: {}
            '''
        }
    }
    stages {
        stage("Linting the project"){
            steps {
              container('build'){
                sh "ls -a"
                sh "pylint --fail-under=5 --disable import-error ./"
              }
            }
        }
        stage("build image and run with compose"){
            steps{
               container('buildkit') {
                 withCredentials([usernamePassword(credentialsId: 'docker-hub-account', usernameVariable: 'DOCKER_USERNAME', passwordVariable: 'DOCKER_PASSWORD')]) {
                sh '''
                # Start buildkitd daemon in the background
                buildkitd --rootless &
                # Wait for socket to be available
                sleep 5

                # Build image but don't push yet - store in BuildKit's local cache
                buildctl build \
                  --frontend=dockerfile.v0 \
                  --local context=. \
                  --local dockerfile=. \
                  --opt filename=weatherapp.dockerfile \
                  --output type=image,name=weatherapp:test,push=false
                
                              
                echo "{\\"auths\\":{\\"https://index.docker.io/v1/\\":{\\"auth\\":\\"`echo -n $DOCKER_USERNAME:$DOCKER_PASSWORD | base64`\\"}}}" > ~/.docker/config.json
               
                # Build and push to Docker Hub
                buildctl build \
                  --frontend=dockerfile.v0 \
                  --local context=. \
                  --local dockerfile=. \
                  --opt filename=weatherapp.dockerfile \
                  --output type=image,name=docker.io/nitzanm594/weatherapp:${BUILD_NUMBER},push=true
                '''
              }
            } 
          }
        }
        stage("Test with custom image") {
          options {
            skipDefaultCheckout(true)
          }
          agent {
            kubernetes {
              cloud 'eks_cluster'
              yaml """
              apiVersion: v1
              kind: Pod
              spec:
                containers:
                - name: weatherapp
                  image: nitzanm594/weatherapp:${env.BUILD_NUMBER}
                  command:
                  - cat
                  tty: true
                  imagePullPolicy: Always
              """
            }
          }
          steps {
            container('weatherapp') {
              sh '''
                if ping -c 1 -p 9090 0.0.0.0 >/dev/null 2>&1;then
                  echo "[OK] Internet Connected!"
	          exit 0
                else
	          echo "No Internet"
	          exit 0
                fi
              '''
              // Add your application-specific test commands here
            }
          }
        }
        stage('helm values edit')
        {
            options {
              skipDefaultCheckout(true)
            }
            steps
            {
              container('build'){
                checkout scmGit(branches: [[name: '*/main']], extensions: [], userRemoteConfigs: [[credentialsId: 'devops-project-id', url: 'http://10.0.1.6/root/helm_weather/']])
                sh """
                sed -i "s/tag: \".*\"/tag: \"${env.BUILD_NUMBER}\"/g" values.yaml
                """
               
                withCredentials([gitUsernamePassword(credentialsId: 'jenkins_token_helm', gitToolName: 'Default')]) {
                    sh "git config --global --add safe.directory /home/jenkins/agent/workspace/weatherapp"
                    sh "git config --global user.email 'nitzanmr@gmail.com'" 
                    sh "git config --global user.name 'Jenkins CI'"           
                    sh "git add values.yaml"

                    sh "git remote -v"  // Verify remote URL
                    sh "git status"     // Check status before committing
                    sh "git commit -m 'changed version in values'"
                    sh "git push origin HEAD:main"
                }
              }
            }
        }
    }   
    post {
        success {
            //Add channel name
            slackSend channel: 'succeeded-build',
            message: "Find Status of Pipeline:- ${currentBuild.currentResult} ${env.JOB_NAME} ${env.BUILD_NUMBER} ${BUILD_URL}"
        }
        failure {
            //Add channel name
            slackSend channel: 'devops-alerts',
            message: "Find Status of Pipeline:- ${currentBuild.currentResult} ${env.JOB_NAME} ${env.BUILD_NUMBER} ${BUILD_URL}"
        }
    }
}
