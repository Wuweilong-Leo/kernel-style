/* test file - before kernel style fix */
#include <linux/module.h>
#include <linux/kernel.h>

// global variable
static int debug_level=3;
static char* device_name="mydev";

// this is a function
int calculate_sum(int a,int b){
    int result=a+b;
    return(result);
}

// another function with wrong pointer style
void* get_buffer(unsigned long size){
    void* ptr;
    ptr=kmalloc(size,GFP_KERNEL);
    if(ptr==NULL){
        printk(KERN_ERR "allocation failed\n");
        return NULL;
    }
    return ptr;
}

// switch statement with wrong case indent
int process_command(int cmd){
    switch(cmd){
        case 1:
            printk("command 1\n");
            break;
        case 2:
            printk("command 2\n");
            break;
        default:
            printk("unknown command\n");
            break;
    }
    return 0;
}

// function with control brace on next line
static int init_module(void)
{
    int ret;
    if(ret<0)
    {
        printk(KERN_ERR "init failed\n");
        return ret;
    }
    else
    {
        printk(KERN_INFO "init success\n");
    }
    return 0;
}

// function with C++ style comments
// This is a header comment
// that spans multiple lines
void helper_function(void){
    // do something
    int x=0;
    // another comment
    x=x+1;
}

// too many blank lines



// after blank lines
void cleanup(void){
    return;
}

// trailing whitespace below

// mixed spaces and tabs for indentation
        int badly_indented(void){
            return 0;
        }
