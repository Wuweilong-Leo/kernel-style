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

// CamelCase identifiers - must be converted to snake_case
int processData(int bufferSize, char *dataBuffer){
    int bytesRemaining = bufferSize;
    int isFirstRun = 1;
    struct nodeInfo *currentNode = NULL;

    if (isFirstRun) {
        currentNode = getActiveNode();
        bytesRemaining = currentNode->dataLength;
    }

    return bytesRemaining;
}

// PascalCase struct name (should NOT be changed - type names controlled by typedef)
struct DeviceConfig {
    int maxRetryCount;
    char *devicePath;
};

// ALL_CAPS macros should NOT be changed
#define MAX_BUFFER_SIZE 1024
#define DEFAULT_TIMEOUT 5000
