package com.jfct.backend.config;

import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import org.springdoc.core.models.GroupedOpenApi;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

@Configuration
   public class Knife4jConfiguration {
   
       @Bean
       public OpenAPI openAPI() {
           return new OpenAPI()
                   .info(new Info()
                           .title("hello-knife4j项目API")
                           .version("1.0")
                           .description("hello-knife4j项目的接口文档"));
       }
       
       @Bean
       public GroupedOpenApi userAPI() {
           return GroupedOpenApi.builder().group("用户信息管理").
                   pathsToMatch("/user/**").
                   build();
       }
   
       @Bean
       public GroupedOpenApi productAPI() {
           return GroupedOpenApi.builder().group("产品信息管理").
                   pathsToMatch("/product/**").
                   build();
       }

    @Bean
    public GroupedOpenApi folderGroup() {
        return GroupedOpenApi.builder()
                .group("文件夹管理")
                .pathsToMatch("/create-random-folder")  // 精确匹配
                .build();
    }


    @Bean
        public GroupedOpenApi restAPI() {
            return GroupedOpenApi.builder().group("其他信息管理").
                    pathsToMatch("/api/**").
                    build();
        }
   }
